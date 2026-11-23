"""The conformance suite (docs/plan/05-connector-sdk.md, section 5).

Platform-level properties every connector must have, checked by running the
real engine (executor + write path) against the connector with a controllable
vendor. A connector test supplies a :class:`Target` adapter and calls the
``check_*`` functions; each raises AssertionError with a precise message.

1. Idempotent       2. Resumable        3. Stable ids       4. Sweep-correct
5. Guarded          6. Tri-state honest 7. Never fabricates 8. Classified
9. Linked           10. Bounded         11. Quiet
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx2

from securefabric_cdk.connector import Connector
from securefabric_cdk.types import NormalizeContext, Skip, Tombstone
from securefabric_db import fetch_all, tenant_tx
from securefabric_domain.runtime import Platform
from securefabric_domain.sync import checkpoints
from securefabric_domain.testing import Tenant, make_connection, rows, sync_stream
from securefabric_schema import FindingRecord, HealthCode, Mode


@dataclass
class Target:
    """How the suite drives one connector."""

    connector_id: str
    credentials: dict[str, Any]
    options: dict[str, Any]
    config: dict[str, Any]
    # Streams in dependency order (resources before findings).
    streams: list[str]
    # Builds a fresh transport for a run (None: the connector's own local transport).
    transport: Callable[[], httpx2.AsyncBaseTransport | None]
    # Removes one record of ``stream`` at the vendor; returns its natural key.
    remove_one: Callable[[str], Awaitable[str]]
    # Makes every listing of ``stream`` return nothing.
    empty_listing: Callable[[str], Awaitable[None]]
    # Restores the vendor after a mutation.
    restore: Callable[[], Awaitable[None]]
    # Injects a status for the next requests of ``stream`` (status -> transport).
    inject: Callable[[str, int], httpx2.AsyncBaseTransport]
    # Raw items for pure checks: stream -> list of raw vendor items.
    samples: Callable[[str], list[dict[str, Any]]]
    # Minimal raw item per stream: only the fields without which there is no record.
    minimal: dict[str, dict[str, Any]] = field(default_factory=dict)
    secrets: list[str] = field(default_factory=list)
    # Per-connector expectations for injected statuses: status -> (outcome kinds, health code).
    expected: dict[int, tuple[tuple[str, ...], HealthCode]] = field(default_factory=dict)


def _table(connector: Connector, stream: str) -> str:
    obj = connector.manifest.stream(stream).object
    return "data.resource" if obj == "resource" else "data.vulnerability_finding"


def _mode(connector: Connector, stream: str) -> Mode:
    return Mode.FULL


async def new_connection(platform: Platform, tenant: Tenant, target: Target) -> UUID:
    return await make_connection(
        platform,
        tenant,
        target.connector_id,
        credentials=target.credentials,
        options=target.options,
        config=target.config,
    )


async def sync_all(
    platform: Platform, tenant: Tenant, cid: UUID, target: Target, *, mode: Mode = Mode.FULL
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for stream in target.streams:
        res = await sync_stream(platform, tenant, cid, stream, mode, transport=target.transport())
        assert res.kind == "completed", f"{stream}: {res.kind} {res.error}"
        out[stream] = res
    return out


async def snapshot(
    platform: Platform, tenant: Tenant, cid: UUID, connector: Connector, streams: list[str]
) -> dict[str, tuple[Any, ...]]:
    snap: dict[str, tuple[Any, ...]] = {}
    for table in sorted({_table(connector, s) for s in streams}):
        for r in await rows(platform, tenant, cid, table):
            snap[f"{table}:{r['natural_key']}"] = (
                r["id"],
                bytes(r["hash"] or b""),
                r["state"],
                r["deleted_at"] is not None,
                r["updated_at"],
            )
    return snap


# ---------------------------------------------------------------- 1. idempotent


async def check_idempotent(platform: Platform, tenant: Tenant, target: Target) -> None:
    connector = platform.registry.get(target.connector_id)
    cid = await new_connection(platform, tenant, target)
    await sync_all(platform, tenant, cid, target)
    before = await snapshot(platform, tenant, cid, connector, target.streams)
    assert before, "the first sync wrote nothing"
    second = await sync_all(platform, tenant, cid, target)
    for stream, res in second.items():
        c = res.counts
        assert (c.added, c.updated, c.deleted) == (0, 0, 0), f"{stream}: re-sync wrote {c}"
    after = await snapshot(platform, tenant, cid, connector, target.streams)
    assert before == after, "re-syncing an unchanged vendor moved updated_at or changed rows"


# ---------------------------------------------------------------- 2. resumable


async def check_resumable(platform: Platform, tenant: Tenant, target: Target, stream: str) -> None:
    connector = platform.registry.get(target.connector_id)
    reference = await new_connection(platform, tenant, target)
    for s in target.streams[: target.streams.index(stream)]:
        await sync_stream(platform, tenant, reference, s, Mode.FULL, transport=target.transport())
    full = await sync_stream(
        platform, tenant, reference, stream, Mode.FULL, transport=target.transport()
    )
    assert full.kind == "completed", full.error
    expected = {
        k.split(":", 1)[1]: v[1:4]
        for k, v in (await snapshot(platform, tenant, reference, connector, [stream])).items()
    }
    pages = full.pages
    assert pages >= 2, f"{stream} needs at least two pages to test resumption (got {pages})"
    for kill_after in range(1, pages):
        cid = await new_connection(platform, tenant, target)
        for s in target.streams[: target.streams.index(stream)]:
            await sync_stream(platform, tenant, cid, s, Mode.FULL, transport=target.transport())
        killed = await sync_stream(
            platform,
            tenant,
            cid,
            stream,
            Mode.FULL,
            max_pages=kill_after,
            transport=target.transport(),
        )
        assert killed.kind == "killed", killed
        resumed = await sync_stream(
            platform,
            tenant,
            cid,
            stream,
            Mode.FULL,
            generation=killed.generation,
            transport=target.transport(),
        )
        assert resumed.kind == "completed", resumed.error
        got = {
            k.split(":", 1)[1]: v[1:4]
            for k, v in (await snapshot(platform, tenant, cid, connector, [stream])).items()
        }
        assert got == expected, f"killed after page {kill_after} and resumed: record set differs"


# ---------------------------------------------------------------- 3. stable ids


async def check_stable_ids(platform: Platform, tenant: Tenant, target: Target) -> None:
    connector = platform.registry.get(target.connector_id)
    cid = await new_connection(platform, tenant, target)
    await sync_all(platform, tenant, cid, target)
    first = {
        k: v[0]
        for k, v in (await snapshot(platform, tenant, cid, connector, target.streams)).items()
    }
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        await checkpoints.clear(conn, cid)  # a reset
    await sync_all(platform, tenant, cid, target)
    again = {
        k: v[0]
        for k, v in (await snapshot(platform, tenant, cid, connector, target.streams)).items()
    }
    assert first == again, "ids changed across a reset"


# ---------------------------------------------------------------- 4. sweep-correct, 5. guarded


async def check_sweep(platform: Platform, tenant: Tenant, target: Target, stream: str) -> None:
    connector = platform.registry.get(target.connector_id)
    table = _table(connector, stream)
    for interrupted in (False, True):
        cid = await new_connection(platform, tenant, target)
        await sync_all(platform, tenant, cid, target)
        removed = await target.remove_one(stream)
        try:
            if interrupted:
                killed = await sync_stream(
                    platform,
                    tenant,
                    cid,
                    stream,
                    Mode.FULL,
                    max_pages=1,
                    transport=target.transport(),
                )
                gen = killed.generation if killed.kind == "killed" else None
                res = await sync_stream(
                    platform,
                    tenant,
                    cid,
                    stream,
                    Mode.FULL,
                    generation=gen,
                    transport=target.transport(),
                )
            else:
                res = await sync_stream(
                    platform, tenant, cid, stream, Mode.FULL, transport=target.transport()
                )
            assert res.kind == "completed", res.error
            deleted = [
                r["natural_key"]
                for r in await rows(platform, tenant, cid, table)
                if r["deleted_at"] is not None and r["stream"] == stream
            ]
            assert deleted == [removed], (
                f"{'resumed' if interrupted else 'full'} pass deleted {deleted}, expected [{removed}]"
            )
        finally:
            await target.restore()


async def check_guarded(platform: Platform, tenant: Tenant, target: Target, stream: str) -> None:
    connector = platform.registry.get(target.connector_id)
    cid = await new_connection(platform, tenant, target)
    await sync_all(platform, tenant, cid, target)
    live_before = [
        r
        for r in await rows(platform, tenant, cid, _table(connector, stream))
        if r["deleted_at"] is None and r["stream"] == stream
    ]
    await target.empty_listing(stream)
    try:
        res = await sync_stream(
            platform, tenant, cid, stream, Mode.FULL, transport=target.transport()
        )
    finally:
        await target.restore()
    assert res.kind == "completed", res.error
    assert res.sweep is not None and res.sweep.aborted, "an empty listing must trip the sweep guard"
    assert res.warning and "sweep aborted" in res.warning
    live_after = [
        r
        for r in await rows(platform, tenant, cid, _table(connector, stream))
        if r["deleted_at"] is None and r["stream"] == stream
    ]
    assert len(live_after) == len(live_before), "the guard must leave the data alone"


# ---------------------------------------------------------------- 6. tri-state honest, 7. never fabricates


def check_tristate(platform: Platform, target: Target) -> None:
    connector = platform.registry.get(target.connector_id)
    for name in target.streams:
        spec = connector.manifest.stream(name)
        if spec.object != "vulnerability_finding":
            continue
        stream = connector.stream(name)
        nctx = NormalizeContext(options=target.options, config=target.config, stream=name)
        for field_name in ("exploitable", "reachability", "has_fix"):
            cap = spec.capabilities.get(field_name)
            if cap is None or cap.supported:
                continue
            for raw in target.samples(name):
                rec = stream.normalize(raw, nctx)
                if isinstance(rec, FindingRecord):
                    assert getattr(rec, field_name) is None, (
                        f"{name}.{field_name} declared unsupported but emitted"
                    )


def check_never_fabricates(platform: Platform, target: Target) -> None:
    """A minimal vendor item yields a record with every optional canonical field
    empty, unless the field is listed in meta_derived (NORM-09)."""
    connector = platform.registry.get(target.connector_id)
    optional_finding = (
        "title",
        "description",
        "has_fix",
        "exploitable",
        "reachability",
        "remediation",
        "analytic_output",
        "ticket",
        "state_changed_at",
    )
    for name, raw in target.minimal.items():
        stream = connector.stream(name)
        rec = stream.normalize(
            json.loads(json.dumps(raw)),
            NormalizeContext(options=target.options, config=target.config, stream=name),
        )
        if isinstance(rec, (Skip, Tombstone)):
            continue
        if isinstance(rec, FindingRecord):
            for f in optional_finding:
                if f in rec.meta_derived:
                    continue
                assert getattr(rec, f) in (None, [], {}), (
                    f"{name}: {f}={getattr(rec, f)!r} fabricated from a minimal item"
                )
            assert rec.vulnerabilities == [] and rec.cve_ids == [], (
                f"{name}: vulnerabilities fabricated"
            )
        else:
            assert (
                rec.url is None
                or "url" in rec.meta_derived
                or raw.get("html_url")
                or raw.get("url")
            ), f"{name}: url fabricated"


# ---------------------------------------------------------------- 8. classified


EXPECTED = {
    401: HealthCode.UNAUTHORIZED,
    403: HealthCode.UNAUTHORIZED,
    404: HealthCode.VENDOR_CLIENT_ERROR,
    500: HealthCode.VENDOR_SERVER_ERROR,
}


async def check_classified(platform: Platform, tenant: Tenant, target: Target, stream: str) -> None:
    cid = await new_connection(platform, tenant, target)
    expected: dict[int, tuple[tuple[str, ...], HealthCode]] = {
        s: (("failed", "retry"), c) for s, c in EXPECTED.items()
    }
    expected.update(target.expected)
    for status, (kinds, code) in expected.items():
        res = await sync_stream(
            platform, tenant, cid, stream, Mode.FULL, transport=target.inject(stream, status)
        )
        assert res.health_code is code, (
            f"injected {status}: got {res.kind}/{res.health_code}, expected {code}"
        )
        assert res.kind in kinds, f"injected {status}: unexpected outcome {res.kind}"
    res = await sync_stream(
        platform, tenant, cid, stream, Mode.FULL, transport=target.inject(stream, 429)
    )
    assert res.kind in ("parked", "retry"), f"injected 429: {res.kind}"
    assert res.health_code is HealthCode.RATE_LIMIT_EXCEEDED, f"injected 429: {res.health_code}"


# ---------------------------------------------------------------- 9. linked


async def check_linked(platform: Platform, tenant: Tenant, target: Target) -> None:
    cid = await new_connection(platform, tenant, target)
    await sync_all(platform, tenant, cid, target)
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        orphans = await fetch_all(
            conn,
            """select f.natural_key from data.vulnerability_finding f
                where f.connection_id = %s and not exists (
                      select 1 from data.finding_resource l join data.resource r
                        on r.connection_id = l.connection_id and r.id = l.resource_id
                       where l.connection_id = f.connection_id and l.finding_id = f.id)""",
            (cid,),
        )
    assert not orphans, f"findings without a resource: {[o['natural_key'] for o in orphans][:5]}"


# ---------------------------------------------------------------- 10. bounded, 11. quiet


async def check_bounded(platform: Platform, tenant: Tenant, target: Target, stream: str) -> None:
    """An incremental run of an unchanged tenant costs at most 5% of the backfill (SYNC-03)."""
    cid = await new_connection(platform, tenant, target)
    for s in target.streams[: target.streams.index(stream)]:
        await sync_stream(platform, tenant, cid, s, Mode.FULL, transport=target.transport())
    backfill = await sync_stream(
        platform, tenant, cid, stream, Mode.BACKFILL, transport=target.transport()
    )
    incr = await sync_stream(
        platform, tenant, cid, stream, Mode.INCREMENTAL, transport=target.transport()
    )
    assert incr.kind == "completed", incr.error
    assert (
        incr.vendor_requests <= max(1, 0.05 * backfill.vendor_requests) or incr.vendor_requests <= 1
    ), f"incremental cost {incr.vendor_requests} vs backfill {backfill.vendor_requests}"


async def check_quiet(platform: Platform, tenant: Tenant, target: Target) -> None:
    cid = await new_connection(platform, tenant, target)
    await sync_all(platform, tenant, cid, target)
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        lines = await fetch_all(
            conn,
            """select e.message, e.http::text as http from obs.operation_event e
                 join obs.operation o on o.id = e.operation_id where o.connection_id = %s""",
            (cid,),
        )
        runs = await fetch_all(
            conn, "select summary::text as s from obs.operation where connection_id = %s", (cid,)
        )
        rows_ = await fetch_all(
            conn,
            "select vendor_attributes_data::text as v from data.vulnerability_finding "
            "where connection_id = %s",
            (cid,),
        )
    blob = "\n".join(
        [str(x) for line in lines for x in line.values()]
        + [r["s"] for r in runs]
        + [r["v"] for r in rows_]
    )
    for secret in target.secrets:
        assert secret not in blob, "a credential leaked into logs, operations or stored rows"
