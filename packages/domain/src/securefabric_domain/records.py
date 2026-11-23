"""The write path (docs/plan/04-sync-engine.md, sections 7 and 8).

:func:`apply_batch` is the only way rows enter ``data.*``. For one batch, in the
caller's transaction:

1. ``pg_advisory_xact_lock`` on (connection, object type)  (STORE-13)
2. ``ts = greatest(clock_timestamp(), head + 1µs)``: a commit-ordered clock (PD-6)
3. stub resources for findings that name a resource we have not seen (NORM-14)
4. hash-gated upsert: unchanged rows only touch ``last_seen_at``/``seen_gen`` (STORE-02/03)
5. platform-derived state: REOPENED, undelete (STORE-04), state_updated_at (NORM-05)
6. state history (STORE-07), finding↔resource links, quarantine (NORM-08)
7. exact counts and the clock in ``stream_head`` / ``object_clock`` (STORE-14)

:func:`sweep` deletes what a complete full pass did not observe, behind the
guard (STORE-05, STORE-06).
"""

import json
import time
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import sql
from pydantic import ValidationError

from securefabric_cdk.types import Tombstone
from securefabric_core.canonical import format_datetime, material_hash
from securefabric_core.crypto import PayloadKeyring
from securefabric_core.ids import record_id
from securefabric_core.telemetry import instruments
from securefabric_db import Conn, fetch_all, fetch_one, fetch_val
from securefabric_schema import (
    FindingRecord,
    FindingState,
    ResourceRecord,
    ResourceState,
    Severity,
    material,
)

VENDOR_DATA_ZLIB_JSON = 0x01
VENDOR_DATA_SEALED = 0x02
SWEEP_GUARD_RATIO = 0.5
SWEEP_GUARD_MIN = 20
SWEEP_BATCH = 1000
OPEN = FindingState.OPEN.value
REOPENED = FindingState.REOPENED.value
DELETED = "DELETED"

_TABLE = {"resource": "data.resource", "vulnerability_finding": "data.vulnerability_finding"}
_KIND = {"resource": "resource", "vulnerability_finding": "finding"}


@dataclass(frozen=True)
class BatchContext:
    environment_id: UUID
    organization_id: UUID
    connection_id: UUID
    stream: str
    object_type: str  # resource | vulnerability_finding
    connector_version: str
    generation: int = 0
    stream_run_id: UUID | None = None
    severity_floor: Severity | None = None
    payload_cipher: PayloadKeyring | None = None  # set when STORE-09 encryption is on


@dataclass
class Invalid:
    """A raw item ``normalize`` could not turn into a valid record."""

    natural_key: str | None
    errors: list[dict[str, Any]]


@dataclass
class BatchResult:
    added: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0
    quarantined: int = 0
    filtered: int = 0
    undeleted: int = 0
    stubs: int = 0
    ts: datetime | None = None
    changed_ids: list[UUID] = field(default_factory=list)

    def add(self, other: "BatchResult") -> None:
        for f in (
            "added",
            "updated",
            "deleted",
            "unchanged",
            "quarantined",
            "filtered",
            "undeleted",
            "stubs",
        ):
            setattr(self, f, getattr(self, f) + getattr(other, f))
        self.changed_ids.extend(other.changed_ids)
        self.ts = other.ts or self.ts


def payload_binding(environment_id: Any, connection_id: Any, object_type: str) -> str:
    return f"{environment_id}/{connection_id}/{object_type}"


def encode_vendor_data(
    payload: dict[str, Any] | None, *, cipher: PayloadKeyring | None = None, bound_to: str = ""
) -> bytes | None:
    """PD-12: opaque bytes with a one-byte format header: 0x01 zlib JSON, 0x02 the same
    sealed with the payload keyring (STORE-09), bound to the row's tenant and stream."""
    if payload is None:
        return None
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str).encode()
    packed = zlib.compress(raw, 6)
    if cipher is not None:
        return bytes([VENDOR_DATA_SEALED]) + cipher.seal(packed, bound_to=bound_to)
    return bytes([VENDOR_DATA_ZLIB_JSON]) + packed


def decode_vendor_data(
    blob: bytes | memoryview | None, *, cipher: PayloadKeyring | None = None, bound_to: str = ""
) -> Any:
    if not blob:
        return None
    data = bytes(blob)
    if data[0] == VENDOR_DATA_ZLIB_JSON:
        return json.loads(zlib.decompress(data[1:]))
    if data[0] == VENDOR_DATA_SEALED:
        if cipher is None:
            raise ValueError("vendor_data is encrypted and no payload key is loaded")
        return json.loads(zlib.decompress(cipher.open(data[1:], bound_to=bound_to)))
    raise ValueError(f"unknown vendor_data format {data[0]}")


def _hex(b: bytes | None) -> str | None:
    return None if b is None else "\\x" + b.hex()


def _ts(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


async def lock_object(conn: Conn, connection_id: UUID, object_type: str) -> None:
    await conn.execute(
        "select pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"{connection_id}:{object_type}",)
    )


async def next_ts(conn: Conn, ctx_env: UUID, connection_id: UUID, object_type: str) -> datetime:
    """The monotonic clock, under the lock: strictly after the last committed head."""
    ts: datetime = await fetch_val(
        conn,
        """
        insert into data.object_clock (connection_id, object_type, environment_id, head_updated_at)
        values (%s, %s, %s, clock_timestamp())
        on conflict (connection_id, object_type) do update
           set head_updated_at = greatest(clock_timestamp(),
                                          data.object_clock.head_updated_at + interval '1 microsecond')
        returning head_updated_at
        """,
        (connection_id, object_type, ctx_env),
    )
    return ts


async def current_generation(conn: Conn) -> int:
    """seen_gen for non-full writes: at least every running pass's generation, so a
    targeted write during a full pass can never make a row look unobserved."""
    val = await fetch_val(conn, "select last_value from sync.generation_seq")
    return int(val or 0)


async def new_generation(conn: Conn) -> int:
    return int(await fetch_val(conn, "select nextval('sync.generation_seq')"))


# ---------------------------------------------------------------- apply_batch


async def apply_batch(
    conn: Conn,
    ctx: BatchContext,
    items: Sequence[ResourceRecord | FindingRecord | Tombstone | Invalid],
    *,
    raw_page_id: UUID | None = None,
) -> BatchResult:
    started = time.perf_counter()
    try:
        return await _apply_batch(conn, ctx, items, raw_page_id=raw_page_id)
    finally:
        if items:
            instruments().batch_write_duration.record(
                time.perf_counter() - started, {"object_type": ctx.object_type}
            )


async def _apply_batch(
    conn: Conn,
    ctx: BatchContext,
    items: Sequence[ResourceRecord | FindingRecord | Tombstone | Invalid],
    *,
    raw_page_id: UUID | None = None,
) -> BatchResult:
    result = BatchResult()
    if not items:
        return result
    table = _TABLE[ctx.object_type]
    # Lock order is always resource, then finding (sweeps cascade the same way).
    if ctx.object_type == "vulnerability_finding":
        await lock_object(conn, ctx.connection_id, "resource")
    await lock_object(conn, ctx.connection_id, ctx.object_type)
    ts = await next_ts(conn, ctx.environment_id, ctx.connection_id, ctx.object_type)
    result.ts = ts
    gen = ctx.generation or await current_generation(conn)

    records: dict[str, ResourceRecord | FindingRecord] = {}
    tombstones: list[str] = []
    invalid: list[Invalid] = []
    for item in items:
        if isinstance(item, Invalid):
            invalid.append(item)
        elif isinstance(item, Tombstone):
            tombstones.append(item.natural_key)
        else:
            if (
                isinstance(item, FindingRecord)
                and ctx.severity_floor is not None
                and item.severity.rank < ctx.severity_floor.rank
                and item.severity is not Severity.UNKNOWN
            ):
                result.filtered += 1
                continue
            records[item.natural_key] = item  # last write wins within a page

    if invalid:
        await _quarantine(conn, ctx, invalid, raw_page_id)
        result.quarantined = len(invalid)

    # --- stubs for referenced resources (NORM-14)
    stub_by_stream: dict[str, int] = {}
    if ctx.object_type == "vulnerability_finding":
        refs: dict[str, Any] = {}
        for rec in records.values():
            assert isinstance(rec, FindingRecord)
            for ref in rec.resources:
                refs.setdefault(ref.natural_key, ref)
        if refs:
            stub_by_stream = await _ensure_stubs(conn, ctx, list(refs.values()), gen)
            result.stubs = sum(stub_by_stream.values())

    keys = list(records) + tombstones
    existing = (
        {
            r["natural_key"]: r
            for r in await fetch_all(
                conn,
                sql.SQL(
                    "select id, natural_key, state, hash, deleted_at, {extra} from {} "
                    "where connection_id = %s and natural_key = any(%s)"
                ).format(
                    sql.SQL(table),
                    extra=sql.SQL(
                        "is_stub, null::timestamptz as state_updated_at"
                        if ctx.object_type == "resource"
                        else "false as is_stub, state_updated_at"
                    ),
                ),
                (ctx.connection_id, keys),
            )
        }
        if keys
        else {}
    )
    pre_delete = await _states_before_delete(
        conn, ctx, [r for r in existing.values() if r["deleted_at"] is not None]
    )

    upserts: list[dict[str, Any]] = []
    touch_ids: list[UUID] = []
    history: list[tuple[UUID, str | None, str, datetime, str]] = []
    link_rows: list[tuple[UUID, UUID, str]] = []
    changed_findings: list[UUID] = []
    live_delta = 0
    deleted_delta = 0
    byte_delta = 0

    for key, rec in records.items():
        rid = record_id(ctx.connection_id, _KIND[ctx.object_type], key)  # type: ignore[arg-type]
        prev = existing.get(key)
        state = rec.state.value
        if isinstance(rec, FindingRecord):
            state = _derive_finding_state(rec.state.value, prev, pre_delete.get(rid))
        mat = material(rec)
        mat["state"] = state
        h = material_hash(mat)
        is_new = prev is None
        was_deleted = prev is not None and prev["deleted_at"] is not None
        if (
            not is_new
            and not was_deleted
            and prev is not None
            and bytes(prev["hash"] or b"") == h
            and not prev["is_stub"]
        ):
            touch_ids.append(rid)
            result.unchanged += 1
            continue
        prev_state = None if prev is None else (DELETED if was_deleted else prev["state"])
        state_changed = prev_state != state
        if is_new:
            result.added += 1
            live_delta += 1
        elif was_deleted:
            result.undeleted += 1
            result.updated += 1
            live_delta += 1
            deleted_delta -= 1
        elif prev is not None and prev["is_stub"]:
            result.updated += 1  # the owning stream filled a placeholder in
        else:
            result.updated += 1
        vendor_blob = encode_vendor_data(
            rec.vendor_data,
            cipher=ctx.payload_cipher,
            bound_to=payload_binding(ctx.environment_id, ctx.connection_id, ctx.object_type),
        )
        byte_delta += len(vendor_blob or b"")
        if state_changed or prev is None:
            if (
                isinstance(rec, FindingRecord)
                and rec.state_changed_at is not None
                and state not in (REOPENED,)
            ):
                state_at = rec.state_changed_at
            elif (
                isinstance(rec, FindingRecord)
                and prev is None
                and state == OPEN
                and rec.vendor.created_at
            ):
                state_at = rec.vendor.created_at
            else:
                state_at = ts
            history.append(
                (rid, prev_state, state, ts, "vendor" if not was_deleted else "platform")
            )
        else:
            state_at = prev["state_updated_at"] if prev is not None else ts
        row = _row(ctx, rec, rid, state, h, vendor_blob, ts, gen, state_at)
        upserts.append(row)
        result.changed_ids.append(rid)
        if isinstance(rec, FindingRecord):
            changed_findings.append(rid)
            for ref in rec.resources:
                link_rows.append(
                    (rid, record_id(ctx.connection_id, "resource", ref.natural_key), ref.role)
                )

    if upserts:
        await _upsert(conn, ctx, upserts)
    if touch_ids:
        await conn.execute(
            sql.SQL(
                "update {} set last_seen_at = %s, seen_gen = greatest(seen_gen, %s) "
                "where connection_id = %s and id = any(%s)"
            ).format(sql.SQL(table)),
            (ts, gen, ctx.connection_id, touch_ids),
        )

    # --- vendor-reported deletions
    for key in tombstones:
        prev = existing.get(key)
        if prev is None or prev["deleted_at"] is not None:
            continue
        await conn.execute(
            sql.SQL(
                "update {} set deleted_at = %s, state = 'DELETED', updated_at = %s, {}"
                "last_seen_at = %s where connection_id = %s and id = %s"
            ).format(sql.SQL(table), _state_at(ctx.object_type)),
            (
                ts,
                ts,
                *(() if ctx.object_type == "resource" else (ts,)),
                ts,
                ctx.connection_id,
                prev["id"],
            ),
        )
        history.append((prev["id"], prev["state"], DELETED, ts, "vendor"))
        result.deleted += 1
        result.changed_ids.append(prev["id"])
        live_delta -= 1
        deleted_delta += 1

    if history:
        await _history(conn, ctx, history)
    if changed_findings:
        await conn.execute(
            "delete from data.finding_resource where connection_id = %s and finding_id = any(%s)",
            (ctx.connection_id, changed_findings),
        )
        if link_rows:
            await conn.execute(
                """insert into data.finding_resource (connection_id, finding_id, resource_id, environment_id, role)
                   select %s, f, r, %s, role from unnest(%s::uuid[], %s::uuid[], %s::text[]) as t(f, r, role)
                   on conflict do nothing""",
                (
                    ctx.connection_id,
                    ctx.environment_id,
                    [r[0] for r in link_rows],
                    [r[1] for r in link_rows],
                    [r[2] for r in link_rows],
                ),
            )

    await _bump_head(
        conn, ctx, ctx.stream, live_delta, deleted_delta, byte_delta, ts, ctx.generation or None
    )
    for stream, n in stub_by_stream.items():
        await _bump_head(conn, ctx, stream, n, 0, 0, ts, None, object_type="resource")
    return result


def _state_at(object_type: str) -> sql.Composable:
    """Findings track when their state changed; resources have no such column."""
    return sql.SQL("") if object_type == "resource" else sql.SQL("state_updated_at = %s, ")


def _derive_finding_state(
    vendor_state: str, prev: dict[str, Any] | None, before_delete: str | None
) -> str:
    """Part 4, section 7: the platform derives REOPENED so every connector behaves alike."""
    if prev is None:
        return vendor_state
    if prev["deleted_at"] is not None:
        if vendor_state == OPEN:
            return REOPENED if before_delete in ("CLOSED", "IGNORED", "REOPENED") else OPEN
        return vendor_state
    if vendor_state == OPEN and prev["state"] in ("CLOSED", "IGNORED", "REOPENED"):
        return REOPENED
    return vendor_state


async def _states_before_delete(
    conn: Conn, ctx: BatchContext, rows: list[dict[str, Any]]
) -> dict[UUID, str]:
    if not rows or ctx.object_type != "vulnerability_finding":
        return {}
    found = await fetch_all(
        conn,
        """select distinct on (record_id) record_id, from_state from data.state_history
            where connection_id = %s and record_id = any(%s) and to_state = 'DELETED'
            order by record_id, at desc""",
        (ctx.connection_id, [r["id"] for r in rows]),
    )
    return {r["record_id"]: r["from_state"] for r in found if r["from_state"]}


def _row(
    ctx: BatchContext,
    rec: ResourceRecord | FindingRecord,
    rid: UUID,
    state: str,
    h: bytes,
    vendor_blob: bytes | None,
    ts: datetime,
    gen: int,
    state_at: datetime | None,
) -> dict[str, Any]:
    base = {
        "id": str(rid),
        "environment_id": str(ctx.environment_id),
        "organization_id": str(ctx.organization_id),
        "connection_id": str(ctx.connection_id),
        "stream": ctx.stream,
        "natural_key": rec.natural_key,
        "type": rec.type.value,
        "state": state,
        "meta_derived": list(rec.meta_derived),
        "connector_version": ctx.connector_version,
        "hash": _hex(h),
        "vendor_data": _hex(vendor_blob),
        "seen_gen": gen,
        "first_seen_at": _ts(ts),
        "last_seen_at": _ts(ts),
        "created_at": _ts(ts),
        "updated_at": _ts(ts),
        "deleted_at": None,
    }
    if isinstance(rec, ResourceRecord):
        d = rec.model_dump(mode="json")
        base.update(
            {
                "name": rec.name,
                "url": rec.url,
                "groups": d["groups"],
                "tags": d["tags"],
                "data": d["data"],
                "cloud_metadata": d["cloud_metadata"],
                "vendor_id": rec.vendor_id,
                "vendor_attributes_data": d["vendor_attributes_data"],
                "is_stub": False,
            }
        )
        return base
    d = rec.model_dump(mode="json")
    v = d["vendor"]
    base.update(
        {
            "title": rec.title,
            "description": rec.description,
            "severity": rec.severity.value,
            "severity_rank": rec.severity.rank,
            "state_updated_at": _ts(state_at),
            "has_fix": rec.has_fix,
            "exploitable": rec.exploitable,
            "reachability": rec.reachability.value if rec.reachability else None,
            "remediation": d["remediation"],
            "analytic": d["analytic"],
            "analytic_output": d["analytic_output"],
            "product": d["product"],
            "ticket": d["ticket"],
            "resource_related": d["resource_related"],
            "vulnerabilities": d["vulnerabilities"],
            "cve_ids": d["cve_ids"],
            "vendor_id": v["id"],
            "vendor_url": v["url"],
            "vendor_severity": v["severity"],
            "vendor_state": v["state"],
            "vendor_created_at": v["created_at"],
            "vendor_updated_at": v["updated_at"],
            "vendor_identifiers": v["vulnerability_identifiers"],
            "vendor_attributes_data": v["data"],
        }
    )
    return base


_RESOURCE_UPDATE = (
    "stream",
    "type",
    "state",
    "name",
    "url",
    "groups",
    "tags",
    "data",
    "cloud_metadata",
    "vendor_id",
    "vendor_attributes_data",
    "vendor_data",
    "is_stub",
    "meta_derived",
    "connector_version",
    "hash",
    "organization_id",
)
_FINDING_UPDATE = (
    "stream",
    "type",
    "title",
    "description",
    "severity",
    "severity_rank",
    "state",
    "state_updated_at",
    "has_fix",
    "exploitable",
    "reachability",
    "remediation",
    "analytic",
    "analytic_output",
    "product",
    "ticket",
    "resource_related",
    "vulnerabilities",
    "cve_ids",
    "meta_derived",
    "vendor_id",
    "vendor_url",
    "vendor_severity",
    "vendor_state",
    "vendor_created_at",
    "vendor_updated_at",
    "vendor_identifiers",
    "vendor_attributes_data",
    "vendor_data",
    "connector_version",
    "hash",
    "organization_id",
)


async def _upsert(conn: Conn, ctx: BatchContext, rows: list[dict[str, Any]]) -> None:
    table = _TABLE[ctx.object_type]
    cols = list(rows[0].keys())
    update_cols = _RESOURCE_UPDATE if ctx.object_type == "resource" else _FINDING_UPDATE
    assignments: list[sql.Composable] = [
        sql.SQL("{c} = excluded.{c}").format(c=sql.Identifier(c)) for c in update_cols
    ]
    assignments += [
        sql.SQL("updated_at = excluded.updated_at"),
        sql.SQL("last_seen_at = excluded.last_seen_at"),
        sql.SQL("seen_gen = greatest({t}.seen_gen, excluded.seen_gen)").format(t=sql.SQL(table)),
        sql.SQL("deleted_at = null"),
    ]
    query = sql.SQL(
        "insert into {t} ({cols}) select {cols} from jsonb_populate_recordset(null::{t}, %s) "
        "on conflict (connection_id, natural_key) do update set {sets}"
    ).format(
        t=sql.SQL(table),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in cols),
        sets=sql.SQL(", ").join(assignments),
    )
    await conn.execute(query, (json.dumps(rows, default=str),))


async def _ensure_stubs(conn: Conn, ctx: BatchContext, refs: list[Any], gen: int) -> dict[str, int]:
    """Placeholder resources so no finding points at nothing (NORM-14). Never moves an
    existing row. The caller holds the resource lock; stubs take their own tick of the
    resource clock so the resource feed stays commit-ordered (PD-6)."""
    known = {
        r["natural_key"]
        for r in await fetch_all(
            conn,
            "select natural_key from data.resource where connection_id = %s and natural_key = any(%s)",
            (ctx.connection_id, [ref.natural_key for ref in refs]),
        )
    }
    refs = [ref for ref in refs if ref.natural_key not in known]
    if not refs:
        return {}
    ts = await next_ts(conn, ctx.environment_id, ctx.connection_id, "resource")
    rows = [
        {
            "id": str(record_id(ctx.connection_id, "resource", ref.natural_key)),
            "environment_id": str(ctx.environment_id),
            "organization_id": str(ctx.organization_id),
            "connection_id": str(ctx.connection_id),
            "stream": ref.stream or "unknown",
            "natural_key": ref.natural_key,
            "type": ref.type.value,
            "state": ResourceState.UNKNOWN.value,
            "name": ref.name,
            "is_stub": True,
            "seen_gen": 0,
            "first_seen_at": _ts(ts),
            "last_seen_at": _ts(ts),
            "created_at": _ts(ts),
            "updated_at": _ts(ts),
            "groups": [],
            "tags": [],
            "data": {},
            "vendor_attributes_data": {},
            "meta_derived": [],
            "connector_version": ctx.connector_version,
        }
        for ref in refs
    ]
    inserted = await fetch_all(
        conn,
        sql.SQL(
            "insert into data.resource ({cols}) select {cols} from jsonb_populate_recordset(null::data.resource, %s) "
            "on conflict (connection_id, natural_key) do nothing returning stream"
        ).format(cols=sql.SQL(", ").join(sql.Identifier(c) for c in rows[0])),
        (json.dumps(rows),),
    )
    counts: dict[str, int] = {}
    for r in inserted:
        counts[r["stream"]] = counts.get(r["stream"], 0) + 1
    return counts


async def _history(
    conn: Conn, ctx: BatchContext, rows: list[tuple[UUID, str | None, str, datetime, str]]
) -> None:
    await conn.execute(
        """insert into data.state_history (environment_id, connection_id, record_id, object_type, from_state,
                                           to_state, at, source, stream_run_id)
           select %s, %s, r, %s, f, t, a, s, %s
             from unnest(%s::uuid[], %s::text[], %s::text[], %s::timestamptz[], %s::text[]) as x(r, f, t, a, s)""",
        (
            ctx.environment_id,
            ctx.connection_id,
            ctx.object_type,
            ctx.stream_run_id,
            [r[0] for r in rows],
            [r[1] for r in rows],
            [r[2] for r in rows],
            [r[3] for r in rows],
            [r[4] for r in rows],
        ),
    )


async def _quarantine(
    conn: Conn, ctx: BatchContext, invalid: list[Invalid], raw_page_id: UUID | None
) -> None:
    for item in invalid:
        await conn.execute(
            """insert into data.quarantine (environment_id, connection_id, stream, stream_run_id, natural_key,
                                            errors, raw_page_id) values (%s, %s, %s, %s, %s, %s, %s)""",
            (
                ctx.environment_id,
                ctx.connection_id,
                ctx.stream,
                ctx.stream_run_id,
                item.natural_key,
                json.dumps(item.errors, default=str),
                raw_page_id,
            ),
        )


async def _bump_head(
    conn: Conn,
    ctx: BatchContext,
    stream: str,
    live: int,
    deleted: int,
    nbytes: int,
    ts: datetime,
    generation: int | None,
    *,
    object_type: str | None = None,
) -> None:
    await conn.execute(
        """insert into data.stream_head (connection_id, stream, environment_id, object_type, live_count,
                                         deleted_count, bytes, head_updated_at, last_generation)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
           on conflict (connection_id, stream) do update
              set live_count = data.stream_head.live_count + excluded.live_count,
                  deleted_count = data.stream_head.deleted_count + excluded.deleted_count,
                  bytes = data.stream_head.bytes + excluded.bytes,
                  head_updated_at = greatest(data.stream_head.head_updated_at, excluded.head_updated_at),
                  last_generation = coalesce(excluded.last_generation, data.stream_head.last_generation)""",
        (
            ctx.connection_id,
            stream,
            ctx.environment_id,
            object_type or ctx.object_type,
            live,
            deleted,
            nbytes,
            ts,
            generation,
        ),
    )


def invalid_from(exc: ValidationError, natural_key: str | None) -> Invalid:
    return Invalid(
        natural_key=natural_key,
        errors=[
            {"loc": ".".join(str(p) for p in e["loc"]), "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ],
    )


# ---------------------------------------------------------------- sweep (STORE-05, STORE-06)


@dataclass
class SweepResult:
    would_delete: int
    live: int
    deleted: int = 0
    cascaded: int = 0
    aborted: bool = False
    confirmed_by_vendor: bool = False


async def sweep_preview(conn: Conn, ctx: BatchContext, generation: int) -> tuple[int, int]:
    table = _TABLE[ctx.object_type]
    row = await fetch_one(
        conn,
        sql.SQL(
            "select count(*) filter (where seen_gen < %s) as would, count(*) as live from {} "
            "where connection_id = %s and stream = %s and deleted_at is null"
        ).format(sql.SQL(table)),
        (generation, ctx.connection_id, ctx.stream),
    )
    assert row is not None
    return int(row["would"]), int(row["live"])


def guard_trips(would_delete: int, live: int) -> bool:
    return would_delete > SWEEP_GUARD_MIN and would_delete > SWEEP_GUARD_RATIO * live


async def sweep(
    conn: Conn, ctx: BatchContext, generation: int, *, confirmed: bool = False
) -> SweepResult:
    """Delete rows of this stream not observed by the full pass ``generation``.

    Call only after ``read()`` returned normally. A guard trip leaves the data
    alone unless the connector confirmed the shrink with the vendor's own count.
    """
    table = _TABLE[ctx.object_type]
    if ctx.object_type == "vulnerability_finding":
        await lock_object(conn, ctx.connection_id, "resource")
    await lock_object(conn, ctx.connection_id, ctx.object_type)
    would, live = await sweep_preview(conn, ctx, generation)
    res = SweepResult(would_delete=would, live=live)
    if would == 0:
        return res
    if guard_trips(would, live) and not confirmed:
        res.aborted = True
        return res
    res.confirmed_by_vendor = confirmed and guard_trips(would, live)
    ts = await next_ts(conn, ctx.environment_id, ctx.connection_id, ctx.object_type)
    deleted: list[tuple[UUID, str]] = []
    while True:
        rows = await fetch_all(
            conn,
            sql.SQL("""with victims as (
                           select id, state from {t}
                            where connection_id = %s and stream = %s and deleted_at is null and seen_gen < %s
                            limit %s)
                       update {t} t set deleted_at = %s, state = 'DELETED', {sa} updated_at = %s
                         from victims v
                        where t.connection_id = %s and t.id = v.id
                       returning t.id, v.state as old_state""").format(
                t=sql.SQL(table), sa=_state_at(ctx.object_type)
            ),
            (
                ctx.connection_id,
                ctx.stream,
                generation,
                SWEEP_BATCH,
                ts,
                *(() if ctx.object_type == "resource" else (ts,)),
                ts,
                ctx.connection_id,
            ),
        )
        if not rows:
            break
        deleted.extend((r["id"], r["old_state"]) for r in rows)
    deleted_ids = [d[0] for d in deleted]
    await _history(conn, ctx, [(rid, old, DELETED, ts, "sweep") for rid, old in deleted])
    res.deleted = len(deleted_ids)
    await _bump_head(conn, ctx, ctx.stream, -res.deleted, res.deleted, 0, ts, generation)
    if ctx.object_type == "resource" and deleted_ids:
        res.cascaded = await _cascade(conn, ctx, deleted_ids)
    return res


async def _cascade(conn: Conn, ctx: BatchContext, resource_ids: list[UUID]) -> int:
    """Findings whose primary resource was deleted go in the same sweep (part 4, section 8)."""
    await lock_object(conn, ctx.connection_id, "vulnerability_finding")
    ts = await next_ts(conn, ctx.environment_id, ctx.connection_id, "vulnerability_finding")
    rows = await fetch_all(
        conn,
        """with victims as (
               select f.id, f.state from data.vulnerability_finding f
                where f.connection_id = %s and f.deleted_at is null and f.id in (
                      select finding_id from data.finding_resource
                       where connection_id = %s and resource_id = any(%s) and role = 'primary'))
           update data.vulnerability_finding f
              set deleted_at = %s, state = 'DELETED', updated_at = %s, state_updated_at = %s
             from victims v
            where f.connection_id = %s and f.id = v.id
           returning f.id, f.stream, v.state as old_state""",
        (ctx.connection_id, ctx.connection_id, resource_ids, ts, ts, ts, ctx.connection_id),
    )
    if rows:
        fctx = BatchContext(
            ctx.environment_id,
            ctx.organization_id,
            ctx.connection_id,
            "cascade",
            "vulnerability_finding",
            ctx.connector_version,
            stream_run_id=ctx.stream_run_id,
        )
        await _history(conn, fctx, [(r["id"], r["old_state"], DELETED, ts, "sweep") for r in rows])
        per_stream: dict[str, int] = {}
        for r in rows:
            per_stream[r["stream"]] = per_stream.get(r["stream"], 0) + 1
        for stream, n in per_stream.items():
            await _bump_head(
                conn, fctx, stream, -n, n, 0, ts, None, object_type="vulnerability_finding"
            )
    return len(rows)


def format_ts(value: datetime) -> str:
    return format_datetime(value)
