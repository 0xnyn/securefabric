"""The scheduler (docs/plan/04-sync-engine.md, sections 3 and 4).

One active scheduler, elected by a session advisory lock. Every second (and on
``NOTIFY`` after an on-demand request or inbound webhook) it runs these steps,
each one short transaction on the cross-tenant ``sf_system`` pool:

1. fire due schedules          2. targeted runs from dirty records
3. admit                       4. expire (the three timeouts of SYNC-09)
5. roll up finished jobs       6. dispatch the outbox (part 7, section 9)

Admission is where priority, fairness and concurrency caps live (SYNC-08/11/12):
Absurd only ever holds work that is allowed to run now, so its FIFO is harmless.
"""

import asyncio
import contextlib
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg

from securefabric_core import get_logger
from securefabric_core.telemetry import instruments
from securefabric_db import Conn, fetch_all, fetch_one, system_tx
from securefabric_domain.events.outbox import emit
from securefabric_domain.runtime import Platform
from securefabric_domain.sync import health
from securefabric_domain.sync.bundle import budget_key_for
from securefabric_domain.sync.jobs import (
    PRIORITY_INTERACTIVE,
    PRIORITY_SCHEDULED,
    create_job,
    jittered,
    mode_for,
)
from securefabric_schema import HealthCode, Mode
from securefabric_tasks.spec import spawn_sql

log = get_logger(__name__)

LEADER_LOCK = 727_401_002
ADMISSION_LOCK = 727_401_003
QUEUE_WAIT_TIMEOUT = timedelta(hours=1)
DEFAULT_RUN_TIMEOUT = timedelta(hours=4)
GAUGE_EVERY_TICKS = 10
TARGETED_BATCH = 200
TARGETED_MAX = 500
ADMIT_PER_TICK = 500

DEFAULT_CAPS = {"connection": 3, "environment": 50, "connector": 500, "queue": 64, "global": 2000}


class Scheduler:
    def __init__(self, platform: Platform) -> None:
        self.p = platform
        self._last_admitted: dict[str, float] = {}
        self._tick_no = 0
        self._maintenance: dict[str, datetime] = {}
        self.maintenance_enabled = True

    @property
    def pool(self) -> Any:
        return self.p.sys_pool

    def now(self) -> datetime:
        return self.p.clock.now()

    async def tick(self) -> dict[str, int]:
        stats = {
            "fired": await self.fire_schedules(),
            "targeted": await self.targeted_from_dirty(),
            "admitted": await self.admit(),
            "expired": await self.expire(),
            "rolled_up": await self.rollup_jobs(),
        }
        from securefabric_domain.events.dispatch import dispatch_outbox

        stats["dispatched"] = await dispatch_outbox(self.p)
        if self.maintenance_enabled:
            from securefabric_domain.maintenance import spawn_due

            stats["maintenance"] = len(await spawn_due(self.p, self._maintenance))
        if self._tick_no % GAUGE_EVERY_TICKS == 0:
            await self.record_gauges()
        self._tick_no += 1
        return stats

    async def record_gauges(self) -> None:
        """OPS-03 scheduler and events gauges: one aggregate query, every few ticks."""
        async with system_tx(self.pool) as conn:
            row = await fetch_one(
                conn,
                """select extract(epoch from now() - (select min(not_before) from sync.stream_run
                              where state in ('QUEUED', 'PARKED', 'RETRY_WAIT') and not_before <= now()))
                              as admission_lag,
                          extract(epoch from now() - (select min(next_run_at) from sync.stream_schedule
                              where state = 'STARTED' and next_run_at <= now())) as lateness,
                          extract(epoch from now() - (select min(created_at) from events.outbox_event
                              where dispatched_at is null)) as outbox_lag""",
            )
            by_state = await fetch_all(
                conn,
                """select state, priority, count(*) as n from sync.stream_run
                    where state in ('QUEUED', 'ADMITTED', 'RUNNING', 'PARKED', 'RETRY_WAIT')
                    group by state, priority""",
            )
        m = instruments()
        row = row or {}
        m.admission_lag.set(float(row.get("admission_lag") or 0))
        m.schedule_lateness.set(float(row.get("lateness") or 0))
        m.outbox_lag.set(float(row.get("outbox_lag") or 0))
        for r in by_state:
            m.runs_by_state.set(int(r["n"]), {"state": r["state"], "priority": int(r["priority"])})

    # ------------------------------------------------------------ 1. fire schedules

    async def fire_schedules(self) -> int:
        now = self.now()
        fired = 0
        async with system_tx(self.pool) as conn:
            due = await fetch_all(
                conn,
                """select s.* from sync.stream_schedule s
                     join control.connection c on c.id = s.connection_id
                    where s.state = 'STARTED' and s.next_run_at <= %s and c.state = 'ACTIVE' and c.deleted_at is null
                    order by s.next_run_at
                    limit 2000
                    for update of s skip locked""",
                (now,),
            )
            by_conn: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
            for s in due:
                by_conn[s["connection_id"]].append(s)
            for connection_id, schedules in by_conn.items():
                connection = await fetch_one(
                    conn, "select * from control.connection where id = %s", (connection_id,)
                )
                assert connection is not None
                manifest = self.p.registry.manifest(connection["connector_id"])
                runs: list[tuple[str, Mode]] = []
                for s in schedules:
                    if s["stream"] not in manifest.stream_names:
                        continue
                    mode = await mode_for(
                        conn, manifest, connection_id, s["stream"], force_full=False, now=now
                    )
                    runs.append((s["stream"], mode))
                    full = mode is Mode.FULL and s["full_every_s"]
                    await conn.execute(
                        """update sync.stream_schedule set next_run_at = %s,
                                  next_full_at = case when %s then %s else next_full_at end
                            where id = %s""",
                        (
                            now + jittered(s["interval_s"]),
                            bool(full),
                            now + timedelta(seconds=s["full_every_s"] or 0),
                            s["id"],
                        ),
                    )
                if runs:
                    key = await budget_key_for(self.p, conn, connection_id)
                    if await create_job(
                        conn,
                        connection,
                        job_type="SCHEDULED",
                        runs=runs,
                        priority=PRIORITY_SCHEDULED,
                        budget_key=key,
                        requested_by="schedule",
                        now=now,
                    ):
                        fired += 1
        return fired

    # ------------------------------------------------------------ 2. targeted refresh

    async def targeted_from_dirty(self) -> int:
        now = self.now()
        created = 0
        async with system_tx(self.pool) as conn:
            groups = await fetch_all(
                conn,
                """select d.connection_id, d.stream, count(*) as n,
                          (array_agg(d.vendor_key order by d.enqueued_at))[1:%s] as keys
                     from sync.dirty_record d join control.connection c on c.id = d.connection_id
                    where c.state = 'ACTIVE' and c.deleted_at is null
                    group by d.connection_id, d.stream""",
                (TARGETED_BATCH,),
            )
            for g in groups:
                busy = await fetch_one(
                    conn,
                    """select 1 from sync.stream_run where connection_id = %s and stream = %s and mode = 'targeted'
                          and state in ('QUEUED', 'ADMITTED', 'RUNNING', 'PARKED', 'RETRY_WAIT')""",
                    (g["connection_id"], g["stream"]),
                )
                if busy:
                    continue
                connection = await fetch_one(
                    conn, "select * from control.connection where id = %s", (g["connection_id"],)
                )
                assert connection is not None
                key = await budget_key_for(self.p, conn, g["connection_id"])
                if g["n"] > TARGETED_MAX:
                    # Cheaper as an ordinary incremental run than hundreds of single fetches.
                    job = await create_job(
                        conn,
                        connection,
                        job_type="WEBHOOK",
                        runs=[(g["stream"], Mode.INCREMENTAL)],
                        priority=PRIORITY_INTERACTIVE,
                        budget_key=key,
                        requested_by="webhook",
                        now=now,
                    )
                    if job:
                        await conn.execute(
                            "delete from sync.dirty_record where connection_id = %s and stream = %s",
                            (g["connection_id"], g["stream"]),
                        )
                        created += 1
                    continue
                if await create_job(
                    conn,
                    connection,
                    job_type="WEBHOOK",
                    runs=[(g["stream"], Mode.TARGETED)],
                    priority=PRIORITY_INTERACTIVE,
                    budget_key=key,
                    requested_by="webhook",
                    now=now,
                    target_keys={g["stream"]: list(g["keys"])},
                ):
                    created += 1
        return created

    # ------------------------------------------------------------ 3. admission

    async def _caps(self, conn: Conn) -> dict[tuple[str, str], int]:
        rows = await fetch_all(
            conn, "select scope_kind, scope_id, max_running from sync.concurrency_limit"
        )
        return {(r["scope_kind"], r["scope_id"]): r["max_running"] for r in rows}

    def _cap(
        self, overrides: dict[tuple[str, str], int], kind: str, scope_id: str, default: int
    ) -> int:
        return overrides.get((kind, scope_id), overrides.get((kind, "*"), default))

    async def admit(self) -> int:
        now = self.now()
        admitted = 0
        async with system_tx(self.pool) as conn:
            await conn.execute("select pg_advisory_xact_lock(%s)", (ADMISSION_LOCK,))
            candidates = await fetch_all(
                conn,
                """select id, environment_id, connection_id, stream, priority, fair_key, budget_key, connector_id,
                  queue,
                          attempt, slice, state, created_at
                     from sync.stream_run
                    where state in ('QUEUED', 'PARKED', 'RETRY_WAIT') and not_before <= %s and not cancel_requested
                    order by priority, created_at
                    limit 5000""",
                (now,),
            )
            if not candidates:
                return 0
            running = await fetch_all(
                conn,
                """select budget_key, connection_id::text as connection_id, environment_id::text as environment_id,
                          connector_id, queue from sync.stream_run where state in ('ADMITTED', 'RUNNING')""",
            )
            overrides = await self._caps(conn)
            counts: dict[tuple[str, str], int] = defaultdict(int)
            for r in running:
                counts[("budget", r["budget_key"])] += 1
                counts[("connection", r["connection_id"])] += 1
                counts[("environment", r["environment_id"])] += 1
                counts[("connector", r["connector_id"])] += 1
                counts[("queue", r["queue"])] += 1
                counts[("global", "*")] += 1

            def fits(run: dict[str, Any]) -> bool:
                manifest_cap = (
                    self.p.registry.manifest(run["connector_id"]).http.budget.max_concurrency
                    if run["connector_id"] in self.p.registry
                    else 4
                )
                checks = [
                    ("budget", run["budget_key"], manifest_cap),
                    ("connection", str(run["connection_id"]), DEFAULT_CAPS["connection"]),
                    ("environment", str(run["environment_id"]), DEFAULT_CAPS["environment"]),
                    ("connector", run["connector_id"], DEFAULT_CAPS["connector"]),
                    ("queue", run["queue"], DEFAULT_CAPS["queue"]),
                    ("global", "*", DEFAULT_CAPS["global"]),
                ]
                return all(
                    counts[(k, sid)] < self._cap(overrides, k, sid, d) for k, sid, d in checks
                )

            def take(run: dict[str, Any]) -> None:
                for k, sid in (
                    ("budget", run["budget_key"]),
                    ("connection", str(run["connection_id"])),
                    ("environment", str(run["environment_id"])),
                    ("connector", run["connector_id"]),
                    ("queue", run["queue"]),
                    ("global", "*"),
                ):
                    counts[(k, sid)] += 1

            by_priority: dict[int, dict[str, deque[dict[str, Any]]]] = defaultdict(
                lambda: defaultdict(deque)
            )
            for c in candidates:
                by_priority[c["priority"]][c["fair_key"]].append(c)
            for priority in sorted(by_priority):
                keyed = by_priority[priority]
                # Round robin across fair keys, least recently admitted first (SYNC-11).
                order = sorted(keyed, key=lambda k: self._last_admitted.get(k, 0.0))
                progress = True
                while progress and admitted < ADMIT_PER_TICK:
                    progress = False
                    for fk in order:
                        queue_ = keyed[fk]
                        pick = next((r for r in queue_ if fits(r)), None)
                        if pick is None:
                            continue
                        queue_.remove(pick)
                        await self._spawn(conn, pick, now)
                        take(pick)
                        self._last_admitted[fk] = (
                            asyncio.get_running_loop().time() + admitted * 1e-6
                        )
                        admitted += 1
                        progress = True
                        if admitted >= ADMIT_PER_TICK:
                            break
        return admitted

    async def _spawn(self, conn: Conn, run: dict[str, Any], now: datetime) -> None:
        next_slice = int(run["slice"]) + 1
        task_id = await spawn_sql(
            conn,
            queue=run["queue"],
            task_name="sync.slice",
            params={
                "run_id": str(run["id"]),
                "environment_id": str(run["environment_id"]),
                "slice": next_slice,
            },
            idempotency_key=f"run:{run['id']}:{run['attempt']}:{next_slice}",
            max_attempts=20,
        )
        await conn.execute(
            """update sync.stream_run set state = 'ADMITTED', admitted_at = %s, slice = %s, absurd_task_id = %s
                where id = %s""",
            (now, next_slice, task_id, run["id"]),
        )

    # ------------------------------------------------------------ 4. expiry

    async def expire(self) -> int:
        now = self.now()
        n = 0
        async with system_tx(self.pool) as conn:
            stale = await fetch_all(
                conn,
                """update sync.stream_run set state = 'EXPIRED', finished_at = %s, health_code = 'EXECUTION_TIMEOUT',
                          error = '{"type": "QueueWaitTimeout", "message": "queued for more than an hour"}'
                    where state = 'QUEUED' and created_at < %s returning id, connection_id""",
                (now, now - QUEUE_WAIT_TIMEOUT),
            )
            for s in stale:
                await raise_alert(
                    conn,
                    "admission_lag",
                    f"run {s['id']}",
                    {"connection_id": str(s["connection_id"])},
                )
            n += len(stale)
            # An ADMITTED run whose Absurd task is gone (or finished without running it)
            # would hold an admission slot forever: put it back in the queue.
            for queue in ("sync_interactive", "sync_bulk"):
                orphaned = await fetch_all(
                    conn,
                    f"""update sync.stream_run r set state = 'QUEUED', absurd_task_id = null
                         where r.state = 'ADMITTED' and r.queue = %s and not exists (
                               select 1 from absurd.t_{queue} t where t.task_id = r.absurd_task_id
                                  and t.state in ('pending', 'running', 'sleeping'))
                        returning r.id""",  # noqa: S608
                    (queue,),
                )
                if orphaned:
                    log.warning("orphaned_admissions_requeued", queue=queue, count=len(orphaned))
                n += len(orphaned)
            late = await fetch_all(
                conn,
                """select id, state, absurd_task_id, queue from sync.stream_run
                    where deadline_at < %s and state in ('ADMITTED', 'RUNNING', 'PARKED', 'RETRY_WAIT')""",
                (now,),
            )
            for r in late:
                if r["state"] == "RUNNING":
                    await conn.execute(
                        "update sync.stream_run set cancel_requested = true where id = %s",
                        (r["id"],),
                    )
                    continue
                code = "RATE_LIMIT_EXCEEDED" if r["state"] == "PARKED" else "EXECUTION_TIMEOUT"
                await conn.execute(
                    """update sync.stream_run set state = 'FAILED', finished_at = %s, health_code = %s,
                              error = %s where id = %s""",
                    (
                        now,
                        code,
                        json.dumps({"type": "DeadlineExceeded", "message": "run deadline passed"}),
                        r["id"],
                    ),
                )
                if r["state"] == "ADMITTED" and r["absurd_task_id"]:
                    await conn.execute(
                        "select absurd.cancel_task(%s, %s)", (r["queue"], r["absurd_task_id"])
                    )
                n += 1
        return n

    # ------------------------------------------------------------ 5. job roll-up

    async def rollup_jobs(self) -> int:
        n = 0
        async with system_tx(self.pool) as conn:
            jobs = await fetch_all(
                conn,
                """select j.* from sync.job j
                    where j.status in ('QUEUED', 'RUNNING')
                      and not exists (select 1 from sync.stream_run r where r.job_id = j.id
                                       and r.state in ('QUEUED', 'ADMITTED', 'RUNNING', 'PARKED', 'RETRY_WAIT'))
                    limit 500
                    for update skip locked""",
            )
            for job in jobs:
                await self._finish_job(conn, job)
                n += 1
        return n

    async def _finish_job(self, conn: Conn, job: dict[str, Any]) -> None:
        runs = await fetch_all(
            conn, "select * from sync.stream_run where job_id = %s order by stream", (job["id"],)
        )
        states = [r["state"] for r in runs]
        if not runs or all(s == "CANCELLED" for s in states):
            status = "CANCELLED"
        elif all(s == "SUCCEEDED" for s in states):
            status = "SUCCESS"
        elif any(s == "SUCCEEDED" for s in states):
            status = "PARTIAL"
        else:
            status = "FAILED"
        codes = [HealthCode(r["health_code"]) for r in runs if r["health_code"]]
        worst = max(codes, key=lambda h: h.severity) if codes else HealthCode.HEALTHY
        failure = next(
            (r["error"].get("message") for r in runs if r["error"] and r["state"] == "FAILED"), None
        )
        now = self.now()
        await conn.execute(
            """update sync.job set status = %s, health_code = %s, failure_reason = %s,
                      started_at = coalesce(started_at, %s), finished_at = %s where id = %s""",
            (status, worst.value, failure, now, now, job["id"]),
        )
        connection = await fetch_one(
            conn,
            "select environment_id, organization_id, connector_id from control.connection "
            "where id = %s",
            (job["connection_id"],),
        )
        if connection is None:
            return
        streams = {
            r["stream"]: {
                "state": r["state"],
                "mode": r["mode"],
                "added": r["added"],
                "updated": r["updated"],
                "deleted": r["deleted"],
                "unchanged": r["unchanged"],
                "quarantined": r["quarantined"],
                "health_code": r["health_code"],
                "warning": r["warning"],
            }
            for r in runs
        }
        totals = {k: sum(s[k] for s in streams.values()) for k in ("added", "updated", "deleted")}
        window = {
            "from": min(
                (r["started_at"] for r in runs if r["started_at"]), default=job["created_at"]
            ),
            "to": now,
        }
        base = {
            "job_id": str(job["id"]),
            "vendor": connection["connector_id"],
            "type": job["type"],
            "status": status,
        }
        env, org, cid = (
            connection["environment_id"],
            connection["organization_id"],
            job["connection_id"],
        )
        await emit(
            conn,
            environment_id=env,
            organization_id=org,
            connection_id=cid,
            type="sync.completed",
            data={
                **base,
                "streams": streams,
                "totals": totals,
                "window": {k: v.isoformat() for k, v in window.items()},
                "has_changes": any(totals.values()),
            },
        )
        if status in ("SUCCESS", "PARTIAL"):
            await emit(
                conn,
                environment_id=env,
                organization_id=org,
                connection_id=cid,
                type="connection.sync.succeeded",
                data={**base, "error": None, "description": None},
            )
        elif status == "FAILED":
            unauthorized = worst in (HealthCode.UNAUTHORIZED, HealthCode.REAUTHORIZATION_REQUIRED)
            await emit(
                conn,
                environment_id=env,
                organization_id=org,
                connection_id=cid,
                type="connection.sync.unauthorized" if unauthorized else "connection.sync.failed",
                data={**base, "error": worst.value, "description": failure},
            )
        await conn.execute(
            "insert into obs.usage_event (environment_id, kind, quantity, detail) values (%s, 'job.finished', 1, %s)",
            (env, json.dumps({"job_id": str(job["id"]), "status": status, **totals})),
        )
        await health.recompute(conn, cid, job_id=job["id"])

    # ------------------------------------------------------------ the loop

    async def run_forever(self, stop: asyncio.Event, *, interval: float = 1.0) -> None:
        """Leader election by a session advisory lock; followers retry every 5 s."""
        while not stop.is_set():
            try:
                async with await psycopg.AsyncConnection.connect(
                    self.p.database_url, autocommit=True
                ) as leader:
                    got = await (
                        await leader.execute("select pg_try_advisory_lock(%s)", (LEADER_LOCK,))
                    ).fetchone()
                    if not got or not got[0]:
                        await _wait(stop, 5.0)
                        continue
                    log.info("scheduler_leader_acquired")
                    from securefabric_domain.sync.jobs import reconcile_all_schedules

                    try:  # a connector release reaches existing connections' schedules
                        n = await reconcile_all_schedules(self.p)
                        log.info("schedules_reconciled", integrations=n)
                    except Exception as exc:  # never block leadership on this
                        log.warning("schedule_reconcile_failed", error=type(exc).__name__)
                    await leader.execute("listen sf_admit")
                    await leader.execute("listen sf_outbox")
                    while not stop.is_set():
                        try:
                            await self.tick()
                        except Exception:
                            log.exception("scheduler_tick_failed")
                        await _wait_notify(leader, stop, interval)
            except (psycopg.OperationalError, OSError):
                log.warning("scheduler_connection_lost")
                await _wait(stop, 2.0)


async def _wait(stop: asyncio.Event, seconds: float) -> None:
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=seconds)


async def _wait_notify(
    conn: psycopg.AsyncConnection[Any], stop: asyncio.Event, seconds: float
) -> None:
    """Sleep until the next tick, or wake early on NOTIFY (on-demand, webhooks, outbox)."""
    try:
        gen = conn.notifies(timeout=seconds, stop_after=1)
        async for _ in gen:
            break
    except TypeError:
        await _wait(stop, seconds)


async def raise_alert(
    conn: Conn, name: str, subject: str | None, detail: dict[str, Any], severity: str = "page"
) -> None:
    from securefabric_domain.obs import RUNBOOKS

    await conn.execute(
        """insert into obs.alert (name, severity, subject, detail, runbook) values (%s, %s, %s, %s, %s)
           on conflict (name, coalesce(subject, '')) where resolved_at is null do nothing""",
        (name, severity, subject, json.dumps(detail, default=str), RUNBOOKS.get(name)),
    )
    log.warning("alert_raised", alert=name, subject=subject)
