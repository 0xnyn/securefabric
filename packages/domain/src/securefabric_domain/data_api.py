"""The data API (docs/plan/07-public-api-and-events.md, sections 3-6).

- **Scope** is exactly one of ``X-CONNECTION-ID`` (Leen) or ``X-ORGANIZATION-ID``
  (ours, additive). A DELETED connection is a 404.
- **Keyset only**, default order ``(updated_at, id)``: the incremental feed. Within a
  connection it cannot skip a change (PD-6); organization feeds hide rows younger
  than 5 seconds because their connections' clocks are independent.
- **Deletes are in the feed** (CDC-02): an ``updatedSince`` read returns deleted rows
  with ``state: DELETED`` and ``deleted_at``; a plain listing excludes them unless
  ``state=DELETED`` is asked for.
- Shapes are Leen V2's (contract-tested against Leen's published schema); our
  fields are additive.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import sql

from securefabric_core import BadRequestError, NotFoundError, ValidationFailedError
from securefabric_core.canonical import format_datetime
from securefabric_db import Conn, fetch_all, fetch_one, tenant_tx
from securefabric_domain.paging import PageOut, clamp_limit, keyset_page
from securefabric_domain.runtime import Platform
from securefabric_domain.tenancy import Principal
from securefabric_schema import (
    FindingState,
    FindingType,
    Reachability,
    ResourceState,
    ResourceType,
    Severity,
)

ORG_FEED_GUARD_S = 5
MAX_IDS = 100

FINDING_SORTS = {
    "updated_at": "f.updated_at",
    "severity": "f.severity_rank",
    "state_updated_at": "coalesce(f.state_updated_at, '-infinity'::timestamptz)",
    "first_seen": "f.first_seen_at",
    "last_seen": "f.last_seen_at",
}
RESOURCE_SORTS = {
    "updated_at": "r.updated_at",
    "first_seen": "r.first_seen_at",
    "last_seen": "r.last_seen_at",
}
_ROW_KEY = {
    "f.updated_at": "updated_at",
    "f.severity_rank": "severity_rank",
    "coalesce(f.state_updated_at, '-infinity'::timestamptz)": "state_updated_at",
    "f.first_seen_at": "first_seen_at",
    "f.last_seen_at": "last_seen_at",
    "r.updated_at": "updated_at",
    "r.first_seen_at": "first_seen_at",
    "r.last_seen_at": "last_seen_at",
}


@dataclass(frozen=True)
class Scope:
    kind: str  # connection | organization
    connection_ids: list[UUID]
    organization_id: UUID | None
    connectors: list[str]

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.organization_id or self.connection_ids[0]}"


async def resolve_scope(
    conn: Conn,
    *,
    connection_header: str | None,
    organization_header: str | None,
    connection_filter: list[UUID] | None,
) -> Scope:
    if bool(connection_header) == bool(organization_header):
        raise BadRequestError(
            "Send exactly one of X-CONNECTION-ID or X-ORGANIZATION-ID.",
            code="scope_header_required",
        )
    if connection_header:
        try:
            cid = UUID(connection_header)
        except ValueError:
            raise BadRequestError(
                "X-CONNECTION-ID must be a UUID.", code="invalid_scope_header"
            ) from None
        row = await fetch_one(
            conn,
            "select id, connector_id, organization_id from control.connection "
            "where id = %s and deleted_at is null",
            (cid,),
        )
        if row is None:
            raise NotFoundError("Connection not found", code="connection_not_found")
        return Scope("connection", [row["id"]], row["organization_id"], [row["connector_id"]])
    try:
        oid = UUID(str(organization_header))
    except ValueError:
        raise BadRequestError(
            "X-ORGANIZATION-ID must be a UUID.", code="invalid_scope_header"
        ) from None
    if (
        await fetch_one(
            conn, "select 1 from control.organization where id = %s and deleted_at is null", (oid,)
        )
        is None
    ):
        raise NotFoundError("Organization not found", code="organization_not_found")
    rows = await fetch_all(
        conn,
        "select id, connector_id from control.connection where organization_id = %s "
        "and deleted_at is null",
        (oid,),
    )
    ids = [r["id"] for r in rows]
    if connection_filter:
        ids = [i for i in ids if i in connection_filter]
    return Scope("organization", ids, oid, sorted({r["connector_id"] for r in rows}))


def parse_sort(value: str | None, allowed: dict[str, str]) -> tuple[str, str, bool]:
    if not value:
        return "updated_at:asc", allowed["updated_at"], False
    field, _, direction = value.partition(":")
    direction = direction or "asc"
    if field not in allowed or direction not in ("asc", "desc"):
        raise BadRequestError(
            f"Unsupported sort {value!r}. Use one of {sorted(allowed)} with :asc or :desc.",
            code="invalid_sort",
            errors=[{"field": "sort", "message": "unsupported"}],
        )
    return f"{field}:{direction}", allowed[field], direction == "desc"


def _enum_list(values: list[str] | None, enum: Any, name: str) -> list[str] | None:
    if not values:
        return None
    out = []
    for v in values:
        up = v.strip().upper()
        if up not in enum.__members__:
            raise ValidationFailedError(
                f"{name} has an unknown value {v!r}.",
                code="invalid_filter",
                errors=[{"field": name, "message": f"unknown value {v!r}"}],
            )
        out.append(up)
    return out


def unsupported_filters(platform: Platform, scope: Scope, used: list[str]) -> list[str]:
    """``X-Unsupported-Filters``: a filter no connector in scope can honour (from capabilities)."""
    out = []
    for f in used:
        supported = False
        for cid in scope.connectors:
            manifest = platform.registry.manifest(cid)
            for s in manifest.streams:
                cap = s.capabilities.get(f)
                if s.object == "vulnerability_finding" and (cap is None or cap.supported):
                    supported = True
        if not supported:
            out.append(f)
    return out


# ---------------------------------------------------------------- rendering


def _ts(v: datetime | None) -> str | None:
    return format_datetime(v) if v else None


def render_resource(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "name": r["name"] or r["natural_key"],
        "type": r["type"],
        "state": r["state"],
        "vendor": r["connector_id"],
        "url": r["url"],
        "groups": r["groups"] or [],
        "tags": r["tags"] or [],
        "first_seen": _ts(r["first_seen_at"]),
        "last_seen": _ts(r["last_seen_at"]),
        "cloud_metadata": r["cloud_metadata"],
        "data": r["data"] or None,
        "vendor_attributes": {
            "id": r["vendor_id"] or r["natural_key"],
            "data": r.get("vendor_attributes_data") or None,
        },
        # additive
        "connection_id": str(r["connection_id"]),
        "organization_id": str(r["organization_id"]),
        "is_stub": r["is_stub"],
        "created_at": _ts(r["created_at"]),
        "updated_at": _ts(r["updated_at"]),
        "deleted_at": _ts(r["deleted_at"]),
        "_meta": {
            "derived": r["meta_derived"] or [],
            "stream": r["stream"],
            "connector_version": r["connector_version"],
            "natural_key": r["natural_key"],
        },
    }


def render_finding(
    f: dict[str, Any], resources: list[dict[str, Any]], enrichment: dict[str, Any] | None
) -> dict[str, Any]:
    return {
        "id": str(f["id"]),
        "title": f["title"],
        "description": f["description"],
        "severity": f["severity"],
        "state": f["state"],
        "type": f["type"],
        "has_fix": f["has_fix"],
        "exploitable": f["exploitable"],
        "reachability": f["reachability"],
        "remediation": f["remediation"],
        "analytic": f["analytic"],
        "analytic_output": f["analytic_output"],
        "product": f["product"],
        "ticket": f["ticket"],
        "resource_related": f["resource_related"] or [],
        "resources": resources,
        "vulnerabilities": f["vulnerabilities"] or [],
        "vendor_attributes": {
            "id": f["vendor_id"] or "",
            "url": f["vendor_url"],
            "severity": f["vendor_severity"],
            "state": f["vendor_state"],
            "created_at": _ts(f["vendor_created_at"]),
            "updated_at": _ts(f["vendor_updated_at"]),
            "vulnerability_identifiers": f["vendor_identifiers"] or [],
            "data": f["vendor_attributes_data"] or None,
        },
        "first_seen": _ts(f["first_seen_at"]),
        "last_seen": _ts(f["last_seen_at"]),
        "state_updated_at": _ts(f["state_updated_at"]),
        # additive
        "connection_id": str(f["connection_id"]),
        "organization_id": str(f["organization_id"]),
        "cve_ids": f["cve_ids"] or [],
        "created_at": _ts(f["created_at"]),
        "updated_at": _ts(f["updated_at"]),
        "deleted_at": _ts(f["deleted_at"]),
        "enrichment": enrichment,
        "_meta": {
            "derived": f["meta_derived"] or [],
            "stream": f["stream"],
            "connector_version": f["connector_version"],
            "natural_key": f["natural_key"],
        },
    }


async def _resources_for(
    conn: Conn, findings: list[dict[str, Any]], include_full: bool
) -> dict[UUID, list[dict[str, Any]]]:
    if not findings:
        return {}
    rows = await fetch_all(
        conn,
        """select l.finding_id, l.role, r.*, c.connector_id
             from data.finding_resource l
             join data.resource r on r.connection_id = l.connection_id and r.id = l.resource_id
             join control.connection c on c.id = r.connection_id
            where l.connection_id = any(%s) and l.finding_id = any(%s)
            order by l.role, r.natural_key""",
        (list({f["connection_id"] for f in findings}), [f["id"] for f in findings]),
    )
    out: dict[UUID, list[dict[str, Any]]] = {}
    for r in rows:
        full = render_resource(r)
        if not include_full:
            full = {
                k: full[k]
                for k in ("id", "name", "type", "state", "vendor", "url", "vendor_attributes")
            }
        full["role"] = r["role"]
        out.setdefault(r["finding_id"], []).append(full)
    return out


def ghsa_ids(f: dict[str, Any]) -> list[str]:
    return [
        i["value"]
        for i in f.get("vendor_identifiers") or []
        if i.get("type") == "GHSA" and i.get("value")
    ]


async def alias_map(conn: Conn, ghsas: list[str]) -> dict[str, str]:
    if not ghsas:
        return {}
    rows = await fetch_all(
        conn, "select alias, cve_id from data.advisory_alias where alias = any(%s)", (ghsas,)
    )
    return {r["alias"]: r["cve_id"] for r in rows}


def effective_cves(f: dict[str, Any], aliases: dict[str, str]) -> list[str]:
    """The finding's CVEs plus those its GHSA advisories alias to (ENR-06)."""
    out = list(f["cve_ids"] or [])
    for g in ghsa_ids(f):
        c = aliases.get(g)
        if c and c not in out:
            out.append(c)
    return out


async def enrichment_for(conn: Conn, cve_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Read-time join with the global CVE mirror (part 7, section 6)."""
    if not cve_ids:
        return {}
    rows = await fetch_all(conn, "select * from data.cve where cve_id = any(%s)", (cve_ids,))
    return {
        r["cve_id"]: {
            "nvd": {
                "description": r["description"],
                "cvss": r["cvss"],
                "cwe": r["cwe"],
                "published_at": _ts(r["published_at"]),
                "modified_at": _ts(r["modified_at"]),
            },
            "kev": r["kev"],
            "epss": r["epss"],
        }
        for r in rows
    }


def _merge_enrichment(
    cves: list[str], table: dict[str, dict[str, Any]], aliased: list[str] | None = None
) -> dict[str, Any] | None:
    hits = {c: table[c] for c in cves if c in table}
    if not hits and not aliased:
        return None
    return {
        "source": "securefabric",
        "cves": hits,
        "aliased_cves": aliased or [],
        "kev": any(bool(v.get("kev")) for v in hits.values()),
        "epss_max": max(
            (float((v.get("epss") or {}).get("epss") or 0) for v in hits.values()), default=None
        ),
    }


# ---------------------------------------------------------------- findings


@dataclass
class FindingQuery:
    severity: list[str] | None = None
    state: list[str] | None = None
    type: list[str] | None = None
    has_fix: bool | None = None
    exploitable: bool | None = None
    reachability: list[str] | None = None
    first_seen_since: datetime | None = None
    last_seen_since: datetime | None = None
    state_updated_since: datetime | None = None
    updated_since: datetime | None = None
    resource_ids: list[UUID] | None = None
    ids: list[UUID] | None = None
    cve_ids: list[str] | None = None
    change_type: list[str] | None = None
    connection_ids: list[UUID] | None = None
    include_resources: bool = False
    sort: str | None = None

    def filters(self) -> dict[str, Any]:
        def j(v: Any) -> Any:
            if isinstance(v, datetime):
                return v.isoformat()
            if isinstance(v, list):
                return [str(x) for x in v]
            return v

        names = {
            "severity": self.severity,
            "state": self.state,
            "type": self.type,
            "has_fix": self.has_fix,
            "exploitable": self.exploitable,
            "reachability": self.reachability,
            "firstSeenSince": self.first_seen_since,
            "lastSeenSince": self.last_seen_since,
            "stateUpdatedSince": self.state_updated_since,
            "updatedSince": self.updated_since,
            "resourceId": self.resource_ids,
            "ids": self.ids,
            "cveId": self.cve_ids,
            "changeType": self.change_type,
            "connectionId": self.connection_ids,
            "include": "resources" if self.include_resources else None,
        }
        return {k: j(v) for k, v in names.items() if v is not None}


def _common_where(
    alias: str, scope: Scope, q: Any, platform_now_guard: bool
) -> tuple[list[sql.Composable], list[Any]]:
    # Plan shape matters (benchmark gate, NFR-04): `connection_id = any($1)` hides a
    # single connection from the planner, which then scans and sorts the whole partition
    # instead of walking the (connection_id, updated_at, id) index; ~100x slower at 100k
    # rows. One connection is an equality; an organization adds organization_id so the
    # (organization_id, updated_at, id) index drives the order.
    where: list[sql.Composable]
    params: list[Any]
    if len(scope.connection_ids) == 1:
        where, params = [sql.SQL(f"{alias}.connection_id = %s")], [scope.connection_ids[0]]
    else:
        where = [sql.SQL(f"{alias}.connection_id = any(%s)")]
        params = [scope.connection_ids]
    if scope.kind == "organization" and scope.organization_id is not None:
        where.insert(0, sql.SQL(f"{alias}.organization_id = %s"))
        params.insert(0, scope.organization_id)
    if platform_now_guard and scope.kind == "organization":
        where.append(sql.SQL(f"{alias}.updated_at < now() - interval '{ORG_FEED_GUARD_S} seconds'"))
    if q.updated_since is not None:
        where.append(sql.SQL(f"{alias}.updated_at >= %s"))
        params.append(q.updated_since)
    if q.ids:
        if len(q.ids) > MAX_IDS:
            raise ValidationFailedError(
                f"ids accepts at most {MAX_IDS} values.",
                code="invalid_filter",
                errors=[{"field": "ids", "message": f"at most {MAX_IDS}"}],
            )
        where.append(sql.SQL(f"{alias}.id = any(%s)"))
        params.append(q.ids)
    states = q.state
    if states and "DELETED" in states:
        pass
    elif q.updated_since is None:
        where.append(sql.SQL(f"{alias}.deleted_at is null"))
    if states:
        where.append(sql.SQL(f"{alias}.state = any(%s)"))
        params.append(states)
    for ct in q.change_type or []:
        if ct not in ("added", "updated", "deleted"):
            raise ValidationFailedError(
                "changeType must be added, updated or deleted.",
                code="invalid_filter",
                errors=[{"field": "changeType", "message": "added|updated|deleted"}],
            )
    if q.change_type:
        since = q.updated_since
        parts = []
        if "added" in q.change_type:
            parts.append(
                f"({alias}.deleted_at is null and "
                + (
                    f"{alias}.created_at >= %s)"
                    if since
                    else f"{alias}.created_at = {alias}.updated_at)"
                )
            )
            if since:
                params.append(since)
        if "updated" in q.change_type:
            parts.append(
                f"({alias}.deleted_at is null and "
                + (
                    f"{alias}.created_at < %s)"
                    if since
                    else f"{alias}.created_at < {alias}.updated_at)"
                )
            )
            if since:
                params.append(since)
        if "deleted" in q.change_type:
            parts.append(f"({alias}.deleted_at is not null)")
        where.append(sql.SQL("(" + " or ".join(parts) + ")"))
    return where, params


async def list_findings(
    platform: Platform,
    principal: Principal,
    q: FindingQuery,
    *,
    connection_header: str | None,
    organization_header: str | None,
    cursor: str | None,
    limit: int | None,
) -> tuple[PageOut[dict[str, Any]], list[str]]:
    principal.require("data:read")
    sort_name, sort_col, desc = parse_sort(q.sort, FINDING_SORTS)
    async with tenant_tx(platform.pool, principal.env) as conn:
        scope = await resolve_scope(
            conn,
            connection_header=connection_header,
            organization_header=organization_header,
            connection_filter=q.connection_ids,
        )
        where, params = _common_where("f", scope, q, True)
        for col, vals in (
            ("f.severity", q.severity),
            ("f.type", q.type),
            ("f.reachability", q.reachability),
        ):
            if vals:
                where.append(sql.SQL(f"{col} = any(%s)"))
                params.append(vals)
        for col, val in (("f.has_fix", q.has_fix), ("f.exploitable", q.exploitable)):
            if val is not None:
                where.append(sql.SQL(f"{col} = %s"))  # a null matches neither true nor false
                params.append(val)
        for col, since in (
            ("f.first_seen_at", q.first_seen_since),
            ("f.last_seen_at", q.last_seen_since),
            ("f.state_updated_at", q.state_updated_since),
        ):
            if since is not None:
                where.append(sql.SQL(f"{col} >= %s"))
                params.append(since)
        if q.cve_ids:
            wanted = [c.upper() for c in q.cve_ids]
            where.append(
                sql.SQL("""(f.cve_ids && %s or exists (
                select 1 from jsonb_array_elements(coalesce(f.vendor_identifiers, '[]')) g
                  join data.advisory_alias a on a.alias = g->>'value' where a.cve_id = any(%s)))""")
            )
            params.extend([wanted, wanted])
        if q.resource_ids:
            where.append(
                sql.SQL("""exists (select 1 from data.finding_resource l where l.connection_id = f.connection_id
                                     and l.finding_id = f.id and l.resource_id = any(%s))""")
            )
            params.append(q.resource_ids)
        key_col = _ROW_KEY[sort_col]
        page = await keyset_page(
            conn,
            key=platform.cursor_key,
            base=sql.SQL("select f.* from data.vulnerability_finding f"),
            where=where,
            params=params,
            sort_name=sort_name,
            sort_exprs=[sort_col, "f.id"],
            sort_keys=lambda r: [
                r[key_col]
                if key_col != "state_updated_at" or r[key_col]
                else datetime.min.replace(tzinfo=r["updated_at"].tzinfo),
                str(r["id"]),
            ],
            descending=desc,
            cursor_token=cursor,
            filters=q.filters(),
            scope=scope.key,
            limit=clamp_limit(limit),
        )
        res = await _resources_for(conn, page.items, q.include_resources)
        aliases = await alias_map(conn, sorted({g for f in page.items for g in ghsa_ids(f)}))
        eff = {f["id"]: effective_cves(f, aliases) for f in page.items}
        enrich = await enrichment_for(conn, sorted({c for cs in eff.values() for c in cs}))
    used = [
        n
        for n, v in (
            ("has_fix", q.has_fix),
            ("exploitable", q.exploitable),
            ("reachability", q.reachability),
        )
        if v is not None
    ]
    items = [
        render_finding(
            f,
            res.get(f["id"], []),
            _merge_enrichment(
                eff[f["id"]], enrich, [c for c in eff[f["id"]] if c not in (f["cve_ids"] or [])]
            ),
        )
        for f in page.items
    ]
    return PageOut(items, page.next_cursor, page.previous_cursor), unsupported_filters(
        platform, scope, used
    )


async def get_finding(
    platform: Platform,
    principal: Principal,
    finding_id: UUID,
    *,
    connection_header: str | None,
    organization_header: str | None,
    include_resources: bool = True,
) -> dict[str, Any]:
    principal.require("data:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        scope = await resolve_scope(
            conn,
            connection_header=connection_header,
            organization_header=organization_header,
            connection_filter=None,
        )
        f = await fetch_one(
            conn,
            "select * from data.vulnerability_finding where id = %s and connection_id = any(%s)",
            (finding_id, scope.connection_ids),
        )
        if f is None:
            raise NotFoundError("Finding not found", code="finding_not_found")
        res = await _resources_for(conn, [f], include_resources)
        eff = effective_cves(f, await alias_map(conn, ghsa_ids(f)))
        enrich = await enrichment_for(conn, eff)
    return render_finding(
        f,
        res.get(f["id"], []),
        _merge_enrichment(eff, enrich, [c for c in eff if c not in (f["cve_ids"] or [])]),
    )


async def finding_history(
    platform: Platform,
    principal: Principal,
    finding_id: UUID,
    *,
    connection_header: str | None,
    organization_header: str | None,
) -> list[dict[str, Any]]:
    principal.require("data:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        scope = await resolve_scope(
            conn,
            connection_header=connection_header,
            organization_header=organization_header,
            connection_filter=None,
        )
        f = await fetch_one(
            conn,
            "select connection_id from data.vulnerability_finding where id = %s and connection_id = any(%s)",
            (finding_id, scope.connection_ids),
        )
        if f is None:
            raise NotFoundError("Finding not found", code="finding_not_found")
        rows = await fetch_all(
            conn,
            """select from_state, to_state, at, source, stream_run_id from data.state_history
                                         where connection_id = %s and record_id = %s order by at, id""",
            (f["connection_id"], finding_id),
        )
    return [{**r, "at": _ts(r["at"])} for r in rows]


async def findings_summary(
    platform: Platform,
    principal: Principal,
    *,
    connection_header: str | None,
    organization_header: str | None,
) -> dict[str, Any]:
    principal.require("data:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        if connection_header or organization_header:
            scope = await resolve_scope(
                conn,
                connection_header=connection_header,
                organization_header=organization_header,
                connection_filter=None,
            )
            ids = scope.connection_ids
        else:
            ids = [
                r["id"]
                for r in await fetch_all(
                    conn, "select id from control.connection where deleted_at is null"
                )
            ]
        rows = await fetch_all(
            conn,
            """select severity, state, type, count(*) as n from data.vulnerability_finding
                                         where connection_id = any(%s) and deleted_at is null group by 1, 2, 3""",
            (ids,),
        )
    out: dict[str, Any] = {
        "total": 0,
        "by_severity": {},
        "by_state": {},
        "by_type": {},
        "open_by_severity": {},
    }
    for r in rows:
        out["total"] += r["n"]
        for k, f in (("by_severity", "severity"), ("by_state", "state"), ("by_type", "type")):
            out[k][r[f]] = out[k].get(r[f], 0) + r["n"]
        if r["state"] in ("OPEN", "REOPENED"):
            out["open_by_severity"][r["severity"]] = (
                out["open_by_severity"].get(r["severity"], 0) + r["n"]
            )
    return out


# ---------------------------------------------------------------- resources


@dataclass
class ResourceQuery:
    name: list[str] | None = None
    vendor: list[str] | None = None
    state: list[str] | None = None
    type: list[str] | None = None
    updated_since: datetime | None = None
    ids: list[UUID] | None = None
    change_type: list[str] | None = None
    connection_ids: list[UUID] | None = None
    sort: str | None = None

    def filters(self) -> dict[str, Any]:
        return {
            k: (
                v.isoformat()
                if isinstance(v, datetime)
                else [str(x) for x in v]
                if isinstance(v, list)
                else v
            )
            for k, v in {
                "name": self.name,
                "vendor": self.vendor,
                "state": self.state,
                "type": self.type,
                "updatedSince": self.updated_since,
                "ids": self.ids,
                "changeType": self.change_type,
                "connectionId": self.connection_ids,
            }.items()
            if v is not None
        }


async def list_resources(
    platform: Platform,
    principal: Principal,
    q: ResourceQuery,
    *,
    connection_header: str | None,
    organization_header: str | None,
    cursor: str | None,
    limit: int | None,
) -> PageOut[dict[str, Any]]:
    principal.require("data:read")
    sort_name, sort_col, desc = parse_sort(q.sort, RESOURCE_SORTS)
    async with tenant_tx(platform.pool, principal.env) as conn:
        scope = await resolve_scope(
            conn,
            connection_header=connection_header,
            organization_header=organization_header,
            connection_filter=q.connection_ids,
        )
        where, params = _common_where("r", scope, q, True)
        for col, vals in (("r.name", q.name), ("r.type", q.type)):
            if vals:
                where.append(sql.SQL(f"{col} = any(%s)"))
                params.append(vals)
        if q.vendor:
            where.append(sql.SQL("c.connector_id = any(%s)"))
            params.append([v.upper() for v in q.vendor])
        key_col = _ROW_KEY[sort_col]
        page = await keyset_page(
            conn,
            key=platform.cursor_key,
            base=sql.SQL(
                "select r.*, c.connector_id from data.resource r join control.connection c on c.id = r.connection_id"
            ),
            where=where,
            params=params,
            sort_name=sort_name,
            sort_exprs=[sort_col, "r.id"],
            sort_keys=lambda r: [r[key_col], str(r["id"])],
            descending=desc,
            cursor_token=cursor,
            filters=q.filters(),
            scope=scope.key,
            limit=clamp_limit(limit),
        )
    return PageOut([render_resource(r) for r in page.items], page.next_cursor, page.previous_cursor)


async def get_resource(
    platform: Platform,
    principal: Principal,
    resource_id: UUID,
    *,
    connection_header: str | None,
    organization_header: str | None,
) -> dict[str, Any]:
    principal.require("data:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        scope = await resolve_scope(
            conn,
            connection_header=connection_header,
            organization_header=organization_header,
            connection_filter=None,
        )
        r = await fetch_one(
            conn,
            """select r.*, c.connector_id from data.resource r join control.connection c on c.id = r.connection_id
                                      where r.id = %s and r.connection_id = any(%s)""",
            (resource_id, scope.connection_ids),
        )
        if r is None:
            raise NotFoundError("Resource not found", code="resource_not_found")
    return render_resource(r)


async def get_cve(platform: Platform, principal: Principal, cve_id: str) -> dict[str, Any]:
    """ENR-04."""
    principal.require("data:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        cid = cve_id.upper()
        alias = await fetch_one(
            conn, "select cve_id from data.advisory_alias where alias = %s", (cid,)
        )
        if alias:
            cid = alias["cve_id"]
        row = await fetch_one(conn, "select * from data.cve where cve_id = %s", (cid,))
        aliases = await fetch_all(
            conn, "select alias, source from data.advisory_alias where cve_id = %s", (cid,)
        )
    if row is None:
        raise NotFoundError("CVE not found in the mirror", code="cve_not_found")
    return {
        **{k: (_ts(v) if isinstance(v, datetime) else v) for k, v in row.items()},
        "aliases": aliases,
    }


VALID = {
    "severity": Severity,
    "state": FindingState,
    "type": FindingType,
    "reachability": Reachability,
    "resource_state": ResourceState,
    "resource_type": ResourceType,
}


def enum_filter(values: list[str] | None, kind: str, name: str) -> list[str] | None:
    return _enum_list(values, VALID[kind], name)
