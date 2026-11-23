"""The internal admin console's backend (OPS-01, OPS-05, OPS-08, RAW-02).

Operators open any account read-only with a stated reason; every access and
repair is audited with ``actor_kind = support``. Repairs that need the vault
(re-normalisation, raw page viewing) run as control tasks.
"""

import asyncio
from dataclasses import replace
from typing import Any
from uuid import UUID

from securefabric_core import (
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from securefabric_db import fetch_all, fetch_one, tenant_tx
from securefabric_domain.runtime import Platform
from securefabric_domain.tenancy import ALL_SCOPES, Principal, audit
from securefabric_tasks.spec import spawn_sql

READ_ONLY = frozenset({"provisioning:read", "data:read"})
REPAIRS = (
    "trigger",
    "pause",
    "resume",
    "reset",
    "renormalize",
    "purge_now",
    "rebuild_counts",
    "reprobe",
)


def require_operator(principal: Principal) -> None:
    if not principal.is_operator:
        raise PermissionDeniedError("Operators only.", code="operator_required")


def _reason(reason: str | None) -> str:
    if not reason or len(reason.strip()) < 5:
        raise BadRequestError(
            "State a support reason (X-Support-Reason, at least 5 characters).",
            code="support_reason_required",
        )
    return reason.strip()[:500]


async def support_principal(
    platform: Platform,
    principal: Principal,
    environment_id: UUID,
    reason: str | None,
    *,
    write: bool = False,
) -> Principal:
    """An operator acting inside a customer environment: read-only unless repairing."""
    require_operator(principal)
    why = _reason(reason)
    async with platform.pool.connection() as conn:
        env = await fetch_one(
            conn, "select * from control.operator_environment(%s)", (environment_id,)
        )
    if env is None:
        raise NotFoundError("Environment not found", code="environment_not_found")
    p = replace(
        principal,
        environment_id=env["id"],
        account_id=env["account_id"],
        scopes=ALL_SCOPES if write else READ_ONLY,
        role="support",
        extra={**principal.extra, "support": True, "support_reason": why},
    )
    async with tenant_tx(platform.pool, env["id"]) as conn:
        await audit(
            conn,
            p,
            "support.access",
            target_kind="environment",
            target_id=env["id"],
            detail={"reason": why, "write": write},
        )
    return p


async def search(platform: Platform, principal: Principal, q: str) -> list[dict[str, Any]]:
    require_operator(principal)
    async with platform.pool.connection() as conn:
        return await fetch_all(conn, "select * from control.operator_search(%s)", (q.strip(),))


async def scheduler_view(platform: Platform, principal: Principal) -> list[dict[str, Any]]:
    require_operator(principal)
    async with platform.pool.connection() as conn:
        return await fetch_all(conn, "select * from control.operator_scheduler()")


async def repair(
    platform: Platform,
    principal: Principal,
    environment_id: UUID,
    connection_id: UUID,
    action: str,
    reason: str | None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if action not in REPAIRS:
        raise BadRequestError(
            f"Unknown repair {action!r}. One of {REPAIRS}.", code="unknown_repair"
        )
    p = await support_principal(platform, principal, environment_id, reason, write=True)
    params = params or {}
    if action in ("pause", "resume"):
        from securefabric_domain.connections import update_connection

        return await update_connection(
            platform, p, connection_id, {"state": "PAUSED" if action == "pause" else "ACTIVE"}
        )
    if action in ("trigger", "reset"):
        from securefabric_domain.sync import jobs
        from securefabric_domain.sync.bundle import budget_key_for

        async with tenant_tx(platform.pool, environment_id) as conn:
            key = await budget_key_for(platform, conn, connection_id)
            if action == "trigger":
                job = await jobs.on_demand(
                    platform,
                    conn,
                    connection_id,
                    streams=params.get("streams"),
                    force_full_refresh=bool(params.get("full")),
                    since=None,
                    requested_by=f"support:{p.actor_id}",
                    budget_key=key,
                )
            else:
                job = await jobs.reset_connection(
                    platform,
                    conn,
                    connection_id,
                    streams=params.get("streams"),
                    wipe=bool(params.get("wipe")),
                    requested_by=f"support:{p.actor_id}",
                    budget_key=key,
                )
            await audit(
                conn,
                p,
                f"support.{action}",
                target_kind="connection",
                target_id=connection_id,
                detail=params,
            )
        return {"job_id": str(job)}
    if action == "rebuild_counts":
        async with tenant_tx(platform.pool, environment_id) as conn:
            await conn.execute(
                "delete from data.stream_head where connection_id = %s", (connection_id,)
            )
            for table, obj in (
                ("data.resource", "resource"),
                ("data.vulnerability_finding", "vulnerability_finding"),
            ):
                await conn.execute(
                    f"""insert into data.stream_head (connection_id, stream, environment_id, object_type,
                                                      live_count, deleted_count, head_updated_at)
                        select connection_id, stream, environment_id, %s, count(*) filter (where deleted_at is null),
                               count(*) filter (where deleted_at is not null), max(updated_at)
                          from {table} where connection_id = %s group by connection_id, stream, environment_id
                        on conflict (connection_id, stream) do update set live_count = excluded.live_count,
                            deleted_count = excluded.deleted_count""",  # noqa: S608
                    (obj, connection_id),
                )
            await audit(
                conn, p, "support.rebuild_counts", target_kind="connection", target_id=connection_id
            )
            heads = await fetch_all(
                conn,
                "select stream, live_count, deleted_count from data.stream_head where connection_id = %s",
                (connection_id,),
            )
        return {"streams": heads}
    # Vault-needing repairs run in the control worker.
    async with tenant_tx(platform.pool, environment_id) as conn:
        row = await fetch_one(
            conn, "select connector_id from control.connection where id = %s", (connection_id,)
        )
        if row is None:
            raise NotFoundError("Connection not found", code="connection_not_found")
        if action == "renormalize":
            # Checked here, not in the worker: a bad request is refused, never queued to fail.
            streams = platform.registry.manifest(row["connector_id"]).stream_names
            if params.get("stream") not in streams:
                raise ValidationFailedError(
                    "renormalize needs params.stream, one of the connector's streams.",
                    code="stream_required",
                    errors=[{"field": "params.stream", "message": "one of " + ", ".join(streams)}],
                )
        task = await spawn_sql(
            conn,
            queue="control",
            task_name="operator.repair",
            params={
                "environment_id": str(environment_id),
                "connection_id": str(connection_id),
                "action": action,
                "params": params,
            },
            max_attempts=1,
        )
        await audit(
            conn,
            p,
            f"support.{action}",
            target_kind="connection",
            target_id=connection_id,
            detail=params,
        )
    return {"task_id": task, "status": "queued"}


async def perform_repair(
    platform: Platform,
    environment_id: UUID,
    connection_id: UUID,
    action: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    if action == "renormalize":
        from securefabric_domain.renormalize import renormalize

        return await renormalize(platform, environment_id, connection_id, params["stream"])
    if action == "purge_now":
        from securefabric_db import system_tx

        async with system_tx(platform.sys_pool) as conn:
            await conn.execute(
                "update control.connection set purge_after = now() where id = %s and state = 'DELETED'",
                (connection_id,),
            )
        from securefabric_domain.maintenance import purge

        return await purge(platform)
    if action == "reprobe":
        from securefabric_domain.connections import verify_connection

        return await verify_connection(platform, environment_id, connection_id, reason="reprobe")
    return {"error": f"unknown repair {action}"}


async def raw_pages(
    platform: Platform,
    principal: Principal,
    environment_id: UUID,
    reason: str | None,
    *,
    connection_id: UUID | None,
    run_id: UUID | None,
) -> list[dict[str, Any]]:
    p = await support_principal(platform, principal, environment_id, reason)
    async with tenant_tx(platform.pool, p.env) as conn:
        return await fetch_all(
            conn,
            """select id, connection_id, stream, stream_run_id, seq, bytes, request_summary, created_at, expires_at
                 from sync.raw_page where (%s::uuid is null or connection_id = %s) and (%s::uuid is null or
                   stream_run_id = %s)
                order by created_at desc, seq limit 200""",
            (connection_id, connection_id, run_id, run_id),
        )


async def view_raw_page(
    platform: Platform,
    principal: Principal,
    environment_id: UUID,
    raw_page_id: UUID,
    reason: str | None,
) -> dict[str, Any]:
    """RAW-02: behind a reason prompt, audited; opened by a worker."""
    p = await support_principal(platform, principal, environment_id, reason)
    async with tenant_tx(platform.pool, p.env) as conn:
        task = await spawn_sql(
            conn,
            queue="control",
            task_name="raw.read",
            params={"environment_id": str(environment_id), "raw_page_id": str(raw_page_id)},
            max_attempts=1,
        )
        await audit(
            conn, p, "support.raw_page_viewed", target_kind="raw_page", target_id=raw_page_id
        )
    for _ in range(150):
        async with platform.pool.connection() as conn:
            snap = await fetch_one(
                conn, "select state, result from absurd.get_task_result('control', %s)", (task,)
            )
        if snap and snap["state"] in ("completed", "failed"):
            return snap["result"] or {"error": "could not open the page"}
        await asyncio.sleep(0.2)
    return {"error": "timed out", "task_id": task}


async def read_raw(platform: Platform, environment_id: UUID, raw_page_id: UUID) -> dict[str, Any]:
    from securefabric_core.redact import redact
    from securefabric_domain.sync.archive import read_raw_page

    page = await read_raw_page(platform, environment_id, raw_page_id)
    if page is None:
        return {"error": "expired or not found"}
    return {
        "id": str(raw_page_id),
        "summary": page["summary"],
        "body": redact(page["body"])[: 512 * 1024],
    }


async def repair_status(platform: Platform, principal: Principal, task_id: UUID) -> dict[str, Any]:
    """Follow a queued repair (it runs in the control worker)."""
    require_operator(principal)
    async with platform.pool.connection() as conn:
        snap = await fetch_one(
            conn,
            "select state, result, failure_reason from absurd.get_task_result('control', %s)",
            (task_id,),
        )
    if snap is None:
        raise NotFoundError("Repair not found", code="repair_not_found")
    failure = snap.get("failure_reason")
    if isinstance(failure, dict):
        failure = {k: failure.get(k) for k in ("name", "message")}  # no traceback over the API
    return {
        "task_id": str(task_id),
        "state": snap["state"],
        "result": snap.get("result"),
        "failure": failure,
    }
