"""Customer-visible operations log (OBS-01/02) and usage counters (BILL-01, BILL-03)."""

import json
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg import sql

from securefabric_core import NotFoundError, get_logger
from securefabric_db import fetch_all, fetch_one, tenant_tx
from securefabric_domain.paging import PageOut, clamp_limit, keyset_page
from securefabric_domain.runtime import Platform
from securefabric_domain.tenancy import Principal

log = get_logger(__name__)


async def list_operations(
    platform: Platform,
    principal: Principal,
    *,
    kind: list[str] | None,
    status: list[str] | None,
    connection_id: UUID | None,
    job_id: UUID | None,
    since: datetime | None,
    cursor: str | None,
    limit: int | None,
) -> PageOut[dict[str, Any]]:
    principal.require("provisioning:read")
    where: list[sql.Composable] = []
    params: list[Any] = []
    for col, val in (("o.kind", kind), ("o.status", status)):
        if val:
            where.append(sql.SQL(f"{col} = any(%s)"))
            params.append(val)
    for col, ident in (("o.connection_id", connection_id), ("o.job_id", job_id)):
        if ident:
            where.append(sql.SQL(f"{col} = %s"))
            params.append(ident)
    # Daily partitions, 30 days served (OBS-03).
    where.append(sql.SQL("o.started_at >= %s"))
    params.append(since or platform.clock.now() - timedelta(days=30))
    filters = {
        "kind": kind,
        "status": status,
        "connectionId": str(connection_id) if connection_id else None,
        "jobId": str(job_id) if job_id else None,
        "since": since.isoformat() if since else None,
    }
    async with tenant_tx(platform.pool, principal.env) as conn:
        page = await keyset_page(
            conn,
            key=platform.cursor_key,
            base=sql.SQL("""select o.*, c.connector_id as vendor,
                                   (select count(*) from obs.operation_event e where e.operation_id = o.id) as
                                       line_count
                              from obs.operation o left join control.connection c on c.id = o.connection_id"""),
            where=where,
            params=params,
            sort_name="started_at:desc",
            sort_exprs=["o.started_at", "o.id"],
            sort_keys=lambda r: [r["started_at"], str(r["id"])],
            descending=True,
            cursor_token=cursor,
            filters=filters,
            scope=f"ops:{principal.env}",
            limit=clamp_limit(limit),
        )
    return page


async def get_operation(
    platform: Platform, principal: Principal, operation_id: UUID
) -> dict[str, Any]:
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        op = await fetch_one(conn, "select * from obs.operation where id = %s", (operation_id,))
        if op is None:
            raise NotFoundError("Operation not found", code="operation_not_found")
        lines = await fetch_all(
            conn,
            "select at, level, kind, message, http from obs.operation_event "
            "where operation_id = %s order by at, id limit 5000",
            (operation_id,),
        )
    return {**op, "line_count": len(lines), "lines": lines}


async def usage(platform: Platform, principal: Principal, *, days: int = 30) -> dict[str, Any]:
    principal.require("provisioning:read")
    since = platform.clock.now().date() - timedelta(days=days)
    async with tenant_tx(platform.pool, principal.env) as conn:
        daily = await fetch_all(
            conn,
            "select * from obs.usage_daily where environment_id = %s and day >= %s order by day",
            (principal.env, since),
        )
        live = await fetch_one(
            conn,
            """select (select count(*) from control.connection where state = 'ACTIVE') as active_connections,
                      (select count(*) from control.connection where state = 'ACTIVE' and health_status =
                          'UNHEALTHY') as unhealthy_connections,
                      (select coalesce(sum(live_count), 0)::bigint from data.stream_head) as records_stored,
                      (select count(*) from sync.job where created_at > now() - interval '24 hours') as jobs_24h,
                      (select count(*) from sync.job where created_at > now() - interval '24 hours' and status =
                          'FAILED') as failed_jobs_24h,
                      (select coalesce(sum(quantity), 0)::bigint from obs.usage_event where kind = 'api.calls'
                          and at > now() - interval '24 hours') as api_calls_24h""",
        )
        by_hour = await fetch_all(
            conn,
            """select date_trunc('hour', at) as hour, sum(quantity)::bigint as api_calls from obs.usage_event
                where kind = 'api.calls' and at > now() - interval '24 hours' group by 1 order by 1""",
        )
    return {
        "live": live,
        "daily": [
            {**d, "day": d["day"].isoformat() if isinstance(d["day"], date) else d["day"]}
            for d in daily
        ],
        "api_calls_by_hour": by_hour,
    }


async def list_alerts(
    platform: Platform, principal: Principal, *, include_resolved: bool = False
) -> list[dict[str, Any]]:
    if not principal.is_operator:
        from securefabric_core import PermissionDeniedError

        raise PermissionDeniedError("Operators only.", code="operator_required")
    async with platform.pool.connection() as conn:
        return await fetch_all(
            conn,
            "select * from obs.alert where (%s or resolved_at is null) order by raised_at desc limit 500",
            (include_resolved,),
        )


async def resolve_alert(
    platform: Platform, principal: Principal, alert_id: UUID, note: str
) -> dict[str, Any]:
    """Operators close an alert once handled (the runbook's last step). Conditions the
    maintenance evaluator re-checks also resolve themselves when they clear."""
    if not principal.is_operator:
        from securefabric_core import PermissionDeniedError

        raise PermissionDeniedError("Operators only.", code="operator_required")
    resolution = {"by": f"{principal.kind}:{principal.actor_id}", "note": note[:500]}
    async with platform.pool.connection() as conn, conn.transaction():
        row = await fetch_one(
            conn,
            """update obs.alert set resolved_at = coalesce(resolved_at, now()),
                      detail = detail || jsonb_build_object('resolution', %s::jsonb)
                where id = %s returning *""",
            (json.dumps(resolution), alert_id),
        )
    if row is None:
        raise NotFoundError("Alert not found", code="alert_not_found")
    log.info("alert_resolved", alert_id=str(alert_id), name=row["name"], by=resolution["by"])
    return row
