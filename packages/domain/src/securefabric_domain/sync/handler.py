"""The slice handler: one Absurd task executes one slice of one stream run.

Outcome table (docs/plan/04-sync-engine.md, section 5):

=================== ============================ ===================================
outcome             run state                    next
=================== ============================ ===================================
completed           SUCCEEDED                    schedule.last_success_at advances
vendor wait > 2 min PARKED, not_before = reset   re-admitted, same attempt
retryable           RETRY_WAIT, backoff          1, 5, 15, 60 min ±20%, then FAILED
auth / config / 4xx FAILED                       no retry
deadline            FAILED EXECUTION_TIMEOUT     checkpoint kept
cancelled           CANCELLED                    checkpoint kept
worker died         (Absurd re-claims the task)  resumes from checkpoint, same attempt
bug                 RETRY_WAIT once, then FAILED INTERNAL_ERROR, pages on-call
=================== ============================ ===================================
"""

import json
import random
import time
from datetime import timedelta
from typing import Any
from uuid import UUID

from securefabric_core import get_logger
from securefabric_core.telemetry import instruments
from securefabric_db import fetch_one, tenant_tx
from securefabric_domain.records import BatchResult
from securefabric_domain.runtime import Platform
from securefabric_domain.sync.executor import SliceInput, SliceOutcome, run_slice
from securefabric_domain.sync.oplog import OperationLog, finish_operation, start_operation
from securefabric_domain.sync.scheduler import DEFAULT_RUN_TIMEOUT
from securefabric_schema import HealthCode, Mode

log = get_logger(__name__)

BACKOFF_S = (60, 300, 900, 3600)
HEARTBEAT_S = 300


def backoff(attempt: int) -> timedelta | None:
    """Delay before attempt ``attempt + 1``, or None when retries are exhausted."""
    if attempt > len(BACKOFF_S):
        return None
    return timedelta(seconds=BACKOFF_S[attempt - 1] * random.uniform(0.8, 1.2))  # noqa: S311


async def _operation_for(
    platform: Platform, run: dict[str, Any], connection: dict[str, Any]
) -> OperationLog:
    async with tenant_tx(platform.pool, run["environment_id"]) as conn:
        op = await fetch_one(
            conn,
            "select id from obs.operation where stream_run_id = %s order by started_at desc limit 1",
            (run["id"],),
        )
    if op is not None:
        return OperationLog(
            platform.pool, environment_id=run["environment_id"], operation_id=op["id"]
        )
    return await start_operation(
        platform.pool,
        environment_id=run["environment_id"],
        kind="sync",
        action=f"{run['stream']}:{run['mode']}",
        connection_id=run["connection_id"],
        organization_id=connection["organization_id"],
        job_id=run["job_id"],
        stream_run_id=run["id"],
    )


async def handle_slice(
    platform: Platform, run_id: UUID, environment_id: UUID, *, heartbeat: Any = None
) -> dict[str, Any]:
    now = platform.clock.now()
    async with tenant_tx(platform.pool, environment_id) as conn:
        run = await fetch_one(
            conn, "select * from sync.stream_run where id = %s for update", (run_id,)
        )
        if run is None or run["state"] not in ("ADMITTED", "RUNNING"):
            return {"run_id": str(run_id), "outcome": "stale"}
        if run["cancel_requested"]:
            await conn.execute(
                "update sync.stream_run set state = 'CANCELLED', finished_at = %s where id = %s",
                (now, run_id),
            )
            return {"run_id": str(run_id), "outcome": "cancelled"}
        connection = await fetch_one(
            conn, "select * from control.connection where id = %s", (run["connection_id"],)
        )
        if connection is None or connection["state"] not in ("ACTIVE",):
            await conn.execute(
                "update sync.stream_run set state = 'CANCELLED', finished_at = %s, warning = %s where id = %s",
                (now, f"connection is {connection['state'] if connection else 'gone'}", run_id),
            )
            return {"run_id": str(run_id), "outcome": "cancelled"}
        deadline = run["deadline_at"] or now + DEFAULT_RUN_TIMEOUT
        if run["generation"] is None and run["mode"] in ("full", "backfill"):
            # Persist the pass generation before any page commits, so a slice that
            # resumes after a worker death continues the same pass (STORE-05).
            from securefabric_domain.records import new_generation

            run["generation"] = await new_generation(conn)
            await conn.execute(
                "update sync.stream_run set generation = %s where id = %s",
                (run["generation"], run_id),
            )
        await conn.execute(
            """update sync.stream_run set state = 'RUNNING', started_at = coalesce(started_at, %s), deadline_at = %s
                where id = %s""",
            (now, deadline, run_id),
        )
        await conn.execute(
            "update sync.job set status = 'RUNNING', started_at = coalesce(started_at, %s) where id = %s and status "
            "= 'QUEUED'",
            (now, run["job_id"]),
        )
    op = await _operation_for(platform, run, connection)

    async def cancel_check() -> bool:
        async with tenant_tx(platform.pool, environment_id) as c:
            r = await fetch_one(
                c, "select cancel_requested from sync.stream_run where id = %s", (run_id,)
            )
        return bool(r and r["cancel_requested"])

    async def on_update(conn: Any, batch: BatchResult, requests: int) -> None:
        await conn.execute(
            """update sync.stream_run set added = added + %s, updated = updated + %s, deleted = deleted + %s,
                      unchanged = unchanged + %s, quarantined = quarantined + %s, pages = pages + 1,
                      vendor_requests = %s where id = %s""",
            (
                batch.added,
                batch.updated,
                batch.deleted,
                batch.unchanged,
                batch.quarantined,
                requests,
                run_id,
            ),
        )

    async def beat() -> None:
        if heartbeat is not None:
            await heartbeat(HEARTBEAT_S)

    slice_started = time.perf_counter()
    outcome = await run_slice(
        platform,
        SliceInput(
            environment_id=environment_id,
            connection_id=run["connection_id"],
            stream=run["stream"],
            mode=Mode(run["mode"]),
            run_id=run_id,
            generation=run["generation"],
            deadline=deadline,
            interactive=run["queue"] == "sync_interactive",
            target_keys=run["target_keys"],
        ),
        op_log=op,
        cancel_check=cancel_check,
        heartbeat=beat,
        on_run_update=on_update,
    )
    _observe(run, outcome, time.perf_counter() - slice_started)
    await apply_outcome(platform, run, outcome, op)
    return {
        "run_id": str(run_id),
        "outcome": outcome.kind,
        "health_code": outcome.health_code.value,
    }


def _observe(run: dict[str, Any], outcome: SliceOutcome, seconds: float) -> None:
    m = instruments()
    attrs = {"connector": run["connector_id"], "stream": run["stream"]}
    m.run_duration.record(seconds, {**attrs, "outcome": outcome.kind})
    m.run_requests.record(outcome.vendor_requests, attrs)
    for change in ("added", "updated", "deleted"):
        n = getattr(outcome.counts, change)
        if n:
            m.records_written.add(n, {**attrs, "change": change})
    if outcome.counts.quarantined:
        m.records_quarantined.add(outcome.counts.quarantined, attrs)


async def apply_outcome(
    platform: Platform, run: dict[str, Any], outcome: SliceOutcome, op: OperationLog
) -> None:
    now = platform.clock.now()
    run_id, env = run["id"], run["environment_id"]
    kind = outcome.kind
    state, not_before, attempt = None, None, run["attempt"]
    if kind == "completed":
        state = "SUCCEEDED"
    elif kind == "parked":
        state, not_before = "PARKED", outcome.reset_at or now + timedelta(minutes=5)
    elif kind in ("retry", "bug"):
        delay = backoff(attempt) if kind == "retry" else (backoff(1) if attempt == 1 else None)
        if delay is None:
            state = "FAILED"
        else:
            state, not_before, attempt = "RETRY_WAIT", now + delay, attempt + 1
    elif kind == "cancelled":
        state = "CANCELLED"
    elif kind == "killed":
        return  # test hook: as if the worker died; Absurd would re-claim
    else:
        state = "FAILED"
    terminal = state in ("SUCCEEDED", "FAILED", "CANCELLED")
    code = outcome.health_code
    if kind == "bug" and state == "FAILED":
        code = HealthCode.INTERNAL_ERROR
    async with tenant_tx(platform.pool, env) as conn:
        await conn.execute(
            """update sync.stream_run
                  set state = %s, not_before = coalesce(%s, not_before), attempt = %s, health_code = %s, error = %s,
                      warning = coalesce(%s, warning), generation = coalesce(generation, %s),
                      vendor_requests = greatest(vendor_requests, %s),
                      finished_at = case when %s then %s else finished_at end
                where id = %s""",
            (
                state,
                not_before,
                attempt,
                code.value,
                json.dumps(outcome.error) if outcome.error else None,
                outcome.warning,
                outcome.generation,
                outcome.vendor_requests,
                terminal,
                now,
                run_id,
            ),
        )
        if state == "SUCCEEDED" and run["mode"] != "targeted":
            await conn.execute(
                "update sync.stream_schedule set last_success_at = %s, last_run_id = %s where connection_id = %s "
                "and stream = %s",
                (now, run_id, run["connection_id"], run["stream"]),
            )
        if outcome.grant is not None:
            grant_status, endpoint, detail = outcome.grant
            await conn.execute(
                """insert into control.connection_grant (connection_id, environment_id, stream, status, endpoint,
                  detail, checked_at)
                   values (%s, %s, %s, %s, %s, %s, now())
                   on conflict (connection_id, stream) do update set status = excluded.status,
                       endpoint = coalesce(excluded.endpoint, control.connection_grant.endpoint),
                       detail = excluded.detail, checked_at = now()""",
                (
                    run["connection_id"],
                    env,
                    run["stream"],
                    grant_status.value,
                    endpoint,
                    (detail or "")[:500],
                ),
            )
        if outcome.sweep is not None and outcome.sweep.aborted:
            from securefabric_domain.sync.scheduler import raise_alert

            await raise_alert(
                conn,
                "sweep_aborted",
                f"{run['connection_id']}/{run['stream']}",
                {"would_delete": outcome.sweep.would_delete, "live": outcome.sweep.live},
            )
        if code is HealthCode.INTERNAL_ERROR and state == "FAILED":
            from securefabric_domain.sync.scheduler import raise_alert

            await raise_alert(conn, "internal_error", str(run_id), {"error": outcome.error})
        if outcome.counts.quarantined and outcome.counts.quarantined > 0.01 * max(
            1, outcome.counts.added + outcome.counts.updated + outcome.counts.unchanged
        ):
            from securefabric_domain.sync.scheduler import raise_alert

            await raise_alert(
                conn,
                "quarantine_spike",
                f"{run['connection_id']}/{run['stream']}",
                {"quarantined": outcome.counts.quarantined},
                severity="ticket",
            )
        await conn.execute("select pg_notify('sf_admit', %s)", (str(run_id),))
    status = {"SUCCEEDED": "success", "FAILED": "failed", "CANCELLED": "cancelled"}.get(
        state or "", "running"
    )
    if outcome.warning and status == "success":
        status = "warning"
    summary = {
        "state": state,
        "health_code": code.value,
        "pages": outcome.pages,
        "vendor_requests": outcome.vendor_requests,
        "added": outcome.counts.added,
        "updated": outcome.counts.updated,
        "deleted": outcome.counts.deleted,
        "unchanged": outcome.counts.unchanged,
        "quarantined": outcome.counts.quarantined,
        "warning": outcome.warning,
        "error": (outcome.error or {}).get("message"),
    }
    if terminal:
        await finish_operation(platform.pool, op, status=status, summary=summary)
    else:
        op.log(
            "info",
            f"{run['stream']}: {state} until {not_before.isoformat() if not_before else '?'}",
        )
        await op.flush()
