"""Schedules, jobs and stream runs (docs/plan/04-sync-engine.md, sections 3, 9).

``sync.stream_run`` is the real queue. The partial unique index on
(connection, stream) for active non-targeted runs enforces SYNC-08 (at most one
active run per stream) in the database, which also bounds queue growth.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from securefabric_cdk.manifest import Manifest
from securefabric_core import ConflictError, NotFoundError
from securefabric_db import Conn, fetch_all, fetch_one
from securefabric_domain.runtime import Platform
from securefabric_schema import Mode, SyncMode

PRIORITY_INTERACTIVE = 0  # on-demand, webhook-targeted
PRIORITY_INITIAL = 1
PRIORITY_SCHEDULED = 2
ACTIVE = ("QUEUED", "ADMITTED", "RUNNING", "PARKED", "RETRY_WAIT")
_ON_CONFLICT = (
    "on conflict (connection_id, stream) where state in "
    "('QUEUED', 'ADMITTED', 'RUNNING', 'PARKED', 'RETRY_WAIT') and mode <> 'targeted' do nothing"
)


def queue_for(priority: int) -> str:
    return "sync_interactive" if priority <= PRIORITY_INITIAL else "sync_bulk"


def stream_interval(
    manifest: Manifest, stream: str, integration: dict[str, Any], options: dict[str, Any]
) -> int:
    return int(
        (options.get("stream_intervals") or {}).get(stream)
        or (integration.get("stream_intervals") or {}).get(stream)
        or manifest.stream(stream).interval.default
    )


def jittered(seconds: float, fraction: float = 0.10) -> timedelta:
    return timedelta(seconds=seconds * random.uniform(1 - fraction, 1 + fraction))  # noqa: S311


def fair_key(connection: dict[str, Any]) -> str:
    return f"{connection['environment_id']}/{connection['organization_id']}"


# ---------------------------------------------------------------- schedules


async def ensure_schedules(
    conn: Conn,
    connection: dict[str, Any],
    integration: dict[str, Any],
    manifest: Manifest,
    options: dict[str, Any],
    now: datetime,
) -> None:
    """One schedule per enabled stream; disabled streams' schedules are deleted."""
    enabled = [s for s in integration["enabled_streams"] if s in manifest.stream_names]
    for stream in enabled:
        spec = manifest.stream(stream)
        interval = stream_interval(manifest, stream, integration, options)
        full_every = spec.full_every if spec.sync_mode is not SyncMode.FULL else None
        await conn.execute(
            """insert into sync.stream_schedule (environment_id, connection_id, stream, interval_s, state,
              next_run_at,
                                                 full_every_s, next_full_at)
               values (%s, %s, %s, %s, 'STARTED', %s, %s, %s)
               on conflict (connection_id, stream) do update
                  set interval_s = excluded.interval_s, full_every_s = excluded.full_every_s,
                      -- a shorter cadence takes effect now, not after the old one elapses
                      next_full_at = case
                          when excluded.full_every_s is null then null
                          else least(coalesce(sync.stream_schedule.next_full_at, excluded.next_full_at),
                                     excluded.next_full_at) end,
                      state = case when sync.stream_schedule.state = 'DELETED' then 'STARTED'
                                   else sync.stream_schedule.state end""",
            (
                connection["environment_id"],
                connection["id"],
                stream,
                interval,
                now + jittered(interval),
                full_every,
                now + timedelta(seconds=full_every) if full_every else None,
            ),
        )
    await conn.execute(
        "update sync.stream_schedule set state = 'DELETED' where connection_id = %s and not (stream = any(%s))",
        (connection["id"], enabled),
    )


async def reconcile_integration_schedules(
    platform: Platform, conn: Conn, integration: dict[str, Any]
) -> None:
    manifest = platform.registry.manifest(integration["connector_id"])
    for c in await fetch_all(
        conn,
        "select * from control.connection where integration_id = %s and state = 'ACTIVE'",
        (integration["id"],),
    ):
        await ensure_schedules(
            conn, c, integration, manifest, c["options"] or {}, platform.clock.now()
        )


async def reconcile_all_schedules(platform: Platform) -> int:
    """Bring every active connection's schedules in line with its connector's current
    manifest and integration (intervals, reconcile cadence, enabled streams). Run by the
    scheduler leader at start, so a connector release reaches existing connections."""
    from securefabric_db import system_tx

    count = 0
    async with system_tx(platform.sys_pool) as conn:
        for integ in await fetch_all(conn, "select * from control.integration"):
            if integ["connector_id"] not in platform.registry:
                continue
            await reconcile_integration_schedules(platform, conn, integ)
            count += 1
    return count


async def set_schedules_state(conn: Conn, connection_id: UUID, state: str) -> None:
    await conn.execute(
        "update sync.stream_schedule set state = %s where connection_id = %s and state <> 'DELETED'",
        (state, connection_id),
    )


# ---------------------------------------------------------------- jobs


async def create_job(
    conn: Conn,
    connection: dict[str, Any],
    *,
    job_type: str,
    runs: list[tuple[str, Mode]],
    priority: int,
    budget_key: str,
    requested_by: str | None = None,
    options: dict[str, Any] | None = None,
    now: datetime,
    target_keys: dict[str, list[str]] | None = None,
) -> UUID | None:
    """Create a job and its runs. Streams that already have an active run are
    skipped (the index makes the insert a no-op). Returns None if nothing was queued."""
    job = await fetch_one(
        conn,
        """insert into sync.job (environment_id, connection_id, type, requested_by, options, created_at)
           values (%s, %s, %s, %s, %s, %s) returning id""",
        (
            connection["environment_id"],
            connection["id"],
            job_type,
            requested_by,
            json.dumps(options or {}),
            now,
        ),
    )
    assert job is not None
    created = 0
    for stream, mode in runs:
        keys = (target_keys or {}).get(stream)
        on_conflict = _ON_CONFLICT if mode is not Mode.TARGETED else ""
        row = await fetch_one(
            conn,
            f"""insert into sync.stream_run (job_id, environment_id, connection_id, stream, mode, priority, fair_key,
                                             budget_key, connector_id, queue, not_before, created_at, target_keys)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) {on_conflict}
                returning id""",  # noqa: S608
            (
                job["id"],
                connection["environment_id"],
                connection["id"],
                stream,
                mode.value,
                priority,
                fair_key(connection),
                budget_key,
                connection["connector_id"],
                queue_for(priority),
                now,
                now,
                keys,
            ),
        )
        if row:
            created += 1
    if not created:
        await conn.execute("delete from sync.job where id = %s", (job["id"],))
        return None
    await conn.execute("select pg_notify('sf_admit', %s)", (str(job["id"]),))
    return UUID(str(job["id"]))


async def mode_for(
    conn: Conn,
    manifest: Manifest,
    connection_id: UUID,
    stream: str,
    *,
    force_full: bool,
    now: datetime,
) -> Mode:
    spec = manifest.stream(stream)
    if spec.sync_mode is SyncMode.FULL or force_full:
        return Mode.FULL
    sched = await fetch_one(
        conn,
        "select last_success_at, next_full_at from sync.stream_schedule "
        "where connection_id = %s and stream = %s",
        (connection_id, stream),
    )
    if sched is None or sched["last_success_at"] is None:
        return Mode.BACKFILL
    if sched["next_full_at"] is not None and sched["next_full_at"] <= now:
        return Mode.FULL
    return Mode.INCREMENTAL


async def initial_job(
    platform: Platform, conn: Conn, connection: dict[str, Any], budget_key: str
) -> UUID | None:
    integ = await fetch_one(
        conn, "select * from control.integration where id = %s", (connection["integration_id"],)
    )
    assert integ is not None
    manifest = platform.registry.manifest(connection["connector_id"])
    now = platform.clock.now()
    await ensure_schedules(conn, connection, integ, manifest, connection["options"] or {}, now)
    streams = [s for s in integ["enabled_streams"] if s in manifest.stream_names]
    blocked = {
        g["stream"]
        for g in await fetch_all(
            conn,
            "select stream from control.connection_grant where connection_id = %s and status in ('UNAUTHORIZED', "
            "'UNSUPPORTED')",
            (connection["id"],),
        )
    }
    runs = [
        (s, Mode.FULL if manifest.stream(s).sync_mode is SyncMode.FULL else Mode.BACKFILL)
        for s in streams
        if s not in blocked
    ]
    return await create_job(
        conn,
        connection,
        job_type="INITIAL",
        runs=runs,
        priority=PRIORITY_INITIAL,
        budget_key=budget_key,
        requested_by="system",
        now=now,
    )


async def on_demand(
    platform: Platform,
    conn: Conn,
    connection_id: UUID,
    *,
    streams: list[str] | None,
    force_full_refresh: bool,
    since: datetime | None,
    requested_by: str,
    budget_key: str,
) -> UUID:
    """SYNC-06. Two quick POSTs return the same job: an active run's job is returned,
    and an active scheduled run is promoted to priority 0."""
    connection = await fetch_one(
        conn,
        "select * from control.connection where id = %s and deleted_at is null for update",
        (connection_id,),
    )
    if connection is None:
        raise NotFoundError("Connection not found", code="connection_not_found")
    if connection["state"] != "ACTIVE":
        raise ConflictError(
            f"The connection is {connection['state']}; only ACTIVE connections sync.",
            code="connection_not_active",
        )
    integ = await fetch_one(
        conn, "select * from control.integration where id = %s", (connection["integration_id"],)
    )
    assert integ is not None
    manifest = platform.registry.manifest(connection["connector_id"])
    wanted = streams or [s for s in integ["enabled_streams"] if s in manifest.stream_names]
    unknown = [s for s in wanted if s not in manifest.stream_names]
    if unknown:
        from securefabric_core import ValidationFailedError

        raise ValidationFailedError(
            f"Unknown streams: {unknown}",
            code="invalid_streams",
            errors=[{"field": "streams", "message": f"unknown: {unknown}"}],
        )
    active = await fetch_all(
        conn,
        """select id, job_id, state from sync.stream_run where connection_id = %s and stream = any(%s)
              and state = any(%s) and mode <> 'targeted' order by created_at""",
        (connection_id, wanted, list(ACTIVE)),
    )
    if active:
        await conn.execute(
            """update sync.stream_run set priority = 0, queue = 'sync_interactive'
                where id = any(%s) and state in ('QUEUED', 'PARKED', 'RETRY_WAIT')""",
            ([a["id"] for a in active],),
        )
        await conn.execute("select pg_notify('sf_admit', %s)", (str(active[0]["job_id"]),))
        return UUID(str(active[0]["job_id"]))
    now = platform.clock.now()
    runs = [
        (
            s,
            await mode_for(
                conn, manifest, connection_id, s, force_full=force_full_refresh, now=now
            ),
        )
        for s in wanted
    ]
    job_id = await create_job(
        conn,
        connection,
        job_type="ON_DEMAND",
        runs=runs,
        priority=PRIORITY_INTERACTIVE,
        budget_key=budget_key,
        requested_by=requested_by,
        now=now,
        options={
            "streams": wanted,
            "force_full_refresh": force_full_refresh,
            "since": since.isoformat() if since else None,
        },
    )
    assert job_id is not None
    return job_id


async def cancel_job(conn: Conn, job_id: UUID, now: datetime) -> dict[str, Any]:
    """SYNC-13: runs not yet executing are cancelled now; a running slice sees the
    flag within a second and stops at the next page boundary."""
    job = await fetch_one(conn, "select * from sync.job where id = %s for update", (job_id,))
    if job is None:
        raise NotFoundError("Job not found", code="job_not_found")
    await conn.execute(
        """update sync.stream_run set state = 'CANCELLED', cancel_requested = true, finished_at = %s,
                  health_code = coalesce(health_code, 'HEALTHY')
            where job_id = %s and state in ('QUEUED', 'PARKED', 'RETRY_WAIT')""",
        (now, job_id),
    )
    await conn.execute(
        "update sync.stream_run set cancel_requested = true where job_id = %s and state in ('ADMITTED', 'RUNNING')",
        (job_id,),
    )
    return job


async def reset_connection(
    platform: Platform,
    conn: Conn,
    connection_id: UUID,
    *,
    streams: list[str] | None,
    wipe: bool,
    requested_by: str,
    budget_key: str,
) -> UUID:
    """SYNC-14: clear checkpoints and queue a full pass. Writes are hash-compared,
    so a reset of an unchanged tenant reports zero added and updated."""
    connection = await fetch_one(
        conn,
        "select * from control.connection where id = %s and deleted_at is null for update",
        (connection_id,),
    )
    if connection is None:
        raise NotFoundError("Connection not found", code="connection_not_found")
    busy = await fetch_one(
        conn,
        "select count(*) as n from sync.stream_run where connection_id = %s and state in ('ADMITTED', 'RUNNING')",
        (connection_id,),
    )
    if busy and busy["n"]:
        raise ConflictError(
            "A sync is running. Cancel it or wait before resetting.", code="sync_in_progress"
        )
    manifest = platform.registry.manifest(connection["connector_id"])
    integ = await fetch_one(
        conn, "select * from control.integration where id = %s", (connection["integration_id"],)
    )
    assert integ is not None
    wanted = streams or [s for s in integ["enabled_streams"] if s in manifest.stream_names]
    await conn.execute(
        "update sync.stream_run set state = 'CANCELLED', finished_at = now() where connection_id = %s "
        "and stream = any(%s) and state in ('QUEUED', 'PARKED', 'RETRY_WAIT')",
        (connection_id, wanted),
    )
    await conn.execute(
        "delete from sync.checkpoint where connection_id = %s and stream = any(%s)",
        (connection_id, wanted),
    )
    if wipe:
        for table in ("data.vulnerability_finding", "data.resource"):
            await conn.execute(
                f"delete from {table} where connection_id = %s and stream = any(%s)",  # noqa: S608
                (connection_id, wanted),
            )
        await conn.execute(
            "delete from data.stream_head where connection_id = %s and stream = any(%s)",
            (connection_id, wanted),
        )
    job_id = await create_job(
        conn,
        connection,
        job_type="ON_DEMAND",
        runs=[(s, Mode.FULL) for s in wanted],
        priority=PRIORITY_INTERACTIVE,
        budget_key=budget_key,
        requested_by=requested_by,
        now=platform.clock.now(),
        options={"reset": True, "wipe": wipe, "streams": wanted},
    )
    assert job_id is not None
    return job_id
