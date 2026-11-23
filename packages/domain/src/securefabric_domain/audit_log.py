"""Reading the audit log (SEC-08): keyset pages, filters, facets and a histogram.

Writes go through :func:`securefabric_domain.tenancy.audit`. The table is
partitioned by month on ``at`` with ``(environment_id, at desc)`` indexed, so
every read here is bounded by a time window and pages on ``(at, id)``; a page
costs the same on the first day as on the millionth event.
"""

from datetime import datetime, timedelta
from typing import Any

from psycopg import sql

from securefabric_core import BadRequestError
from securefabric_db import fetch_all, fetch_one, tenant_tx
from securefabric_domain.paging import PageOut, clamp_limit, keyset_page
from securefabric_domain.runtime import Platform
from securefabric_domain.tenancy import Principal

#: How far back a read goes when the caller gives no ``since``.
DEFAULT_WINDOW = timedelta(days=90)
#: Histogram bucket count; the bucket width follows from the window.
BUCKETS = 60


async def _window(
    conn: Any, since: datetime | None, until: datetime | None
) -> tuple[datetime, datetime]:
    """The read window, defaulting to the last 90 days by the database's clock
    (the clock that stamped ``at``)."""
    if until is None:
        row = await fetch_one(conn, "select now() as now")
        until = row["now"] if row else None
    assert until is not None
    start = since or until - DEFAULT_WINDOW
    if start >= until:
        raise BadRequestError("since must be earlier than until.", code="invalid_window")
    return start, until


def _filters(
    *,
    action: list[str] | None,
    actor_kind: list[str] | None,
    actor_id: str | None,
    target_kind: list[str] | None,
    target_id: str | None,
    search: str | None,
) -> tuple[list[sql.Composable], list[Any]]:
    where: list[sql.Composable] = []
    params: list[Any] = []
    for column, values in (
        ("action", action),
        ("actor_kind", actor_kind),
        ("target_kind", target_kind),
    ):
        if values:
            where.append(sql.SQL("{} = any(%s)").format(sql.Identifier("e", column)))
            params.append(values)
    for column, value in (("actor_id", actor_id), ("target_id", target_id)):
        if value:
            where.append(sql.SQL("{} = %s").format(sql.Identifier("e", column)))
            params.append(value)
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        where.append(
            sql.SQL(
                "(e.action ilike %s or e.target_id ilike %s or e.actor_id ilike %s"
                " or e.request_id ilike %s or e.detail::text ilike %s)"
            )
        )
        params.extend([like] * 5)
    return where, params


async def list_events(
    platform: Platform,
    principal: Principal,
    *,
    action: list[str] | None = None,
    actor_kind: list[str] | None = None,
    actor_id: str | None = None,
    target_kind: list[str] | None = None,
    target_id: str | None = None,
    search: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> PageOut[dict[str, Any]]:
    """Newest first. Cursors are bound to the filters they were made with."""
    where, params = _filters(
        action=action,
        actor_kind=actor_kind,
        actor_id=actor_id,
        target_kind=target_kind,
        target_id=target_id,
        search=search,
    )
    filters = {
        "action": action,
        "actorKind": actor_kind,
        "actorId": actor_id,
        "targetKind": target_kind,
        "targetId": target_id,
        "search": search,
        "since": since.isoformat() if since else None,
        "until": until.isoformat() if until else None,
    }
    async with tenant_tx(platform.pool, principal.env) as conn:
        start, end = await _window(conn, since, until)
        return await keyset_page(
            conn,
            key=platform.cursor_key,
            base=sql.SQL("select e.* from obs.audit_event e"),
            where=[
                sql.SQL("e.environment_id = %s"),
                sql.SQL("e.at >= %s"),
                sql.SQL("e.at <= %s"),
                *where,
            ],
            params=[principal.env, start, end, *params],
            sort_name="at:desc",
            sort_exprs=["e.at", "e.id"],
            sort_keys=lambda r: [r["at"], str(r["id"])],
            descending=True,
            cursor_token=cursor,
            filters=filters,
            scope=f"audit:{principal.env}",
            limit=clamp_limit(limit),
        )


async def facets(
    platform: Platform,
    principal: Principal,
    *,
    action: list[str] | None = None,
    actor_kind: list[str] | None = None,
    actor_id: str | None = None,
    target_kind: list[str] | None = None,
    target_id: str | None = None,
    search: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, Any]:
    """Counts per action, actor kind, actor and target kind, plus a histogram.

    The same filters as :func:`list_events`, so the counts describe exactly
    what the list would page through.
    """
    where, params = _filters(
        action=action,
        actor_kind=actor_kind,
        actor_id=actor_id,
        target_kind=target_kind,
        target_id=target_id,
        search=search,
    )
    clauses = sql.SQL(" and ").join(
        [sql.SQL("e.environment_id = %s"), sql.SQL("e.at >= %s"), sql.SQL("e.at <= %s"), *where]
    )
    async with tenant_tx(platform.pool, principal.env) as conn:
        start, end = await _window(conn, since, until)
        args = [principal.env, start, end, *params]
        bucket_s = max(60, int((end - start).total_seconds() // BUCKETS))
        total = await fetch_all(
            conn,
            sql.SQL("select count(*) as n from obs.audit_event e where {}").format(clauses),
            args,
        )
        groups: dict[str, list[dict[str, Any]]] = {}
        for name in ("action", "actor_kind", "actor_id", "target_kind"):
            rows = await fetch_all(
                conn,
                sql.SQL(
                    "select {col} as value, count(*) as count from obs.audit_event e"
                    " where {where} and {col} is not null group by 1 order by 2 desc, 1 limit 100"
                ).format(col=sql.Identifier("e", name), where=clauses),
                args,
            )
            groups[name] = [{"value": r["value"], "count": r["count"]} for r in rows]
        histogram = await fetch_all(
            conn,
            sql.SQL(
                "select to_timestamp(floor(extract(epoch from e.at) / %s) * %s) as at, count(*) as count"
                " from obs.audit_event e where {} group by 1 order by 1"
            ).format(clauses),
            [bucket_s, bucket_s, *args],
        )
    return {
        "total": total[0]["n"] if total else 0,
        "since": start,
        "until": end,
        "bucket_seconds": bucket_s,
        "histogram": histogram,
        **groups,
    }
