"""The write path: apply_batch semantics, sweep, and the CDC-01 concurrency property."""

import asyncio
import random
from datetime import UTC, datetime
from typing import Any

import pytest

from securefabric_cdk.types import Tombstone
from securefabric_db import fetch_all, fetch_required, tenant_tx
from securefabric_domain import records
from securefabric_domain.records import BatchContext, Invalid
from securefabric_domain.testing import make_connection
from securefabric_schema import (
    FindingRecord,
    FindingState,
    FindingType,
    ResourceRecord,
    ResourceRef,
    ResourceType,
    Severity,
)

pytestmark = pytest.mark.integration


def finding(n: int, state: FindingState = FindingState.OPEN, **kw: Any) -> FindingRecord:
    base: dict[str, Any] = {
        "natural_key": f"f:{n}",
        "type": FindingType.HOST,
        "title": f"finding {n}",
        "severity": Severity.HIGH,
        "state": state,
        "resources": [
            ResourceRef(
                natural_key=f"h:{n % 3}", type=ResourceType.HOST, name=f"h{n % 3}", stream="hosts"
            )
        ],
    }
    base.update(kw)
    return FindingRecord(**base)


def host(n: int, **kw: Any) -> ResourceRecord:
    return ResourceRecord(natural_key=f"h:{n}", type=ResourceType.HOST, name=f"host-{n}", **kw)


async def ctx_for(
    platform,
    tenant,
    object_type: str = "vulnerability_finding",
    stream: str = "findings",
    gen: int = 0,
):
    cid = await make_connection(platform, tenant, credentials={"api_key": "sbx_x_key"})
    return BatchContext(
        tenant.environment_id,
        tenant.organization_id,
        cid,
        stream,
        object_type,
        "1.0.0",
        generation=gen,
    )


async def apply(platform, tenant, ctx, items):
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        return await records.apply_batch(conn, ctx, items)


async def row(platform, tenant, ctx, key, table="data.vulnerability_finding"):
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        return await fetch_required(
            conn,
            f"select * from {table} where connection_id = %s and natural_key = %s",  # noqa: S608
            (ctx.connection_id, key),
        )


async def history(platform, tenant, ctx, record_id):
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        return await fetch_all(
            conn,
            "select from_state, to_state, source from data.state_history where "
            "connection_id = %s and record_id = %s order by at, id",
            (ctx.connection_id, record_id),
        )


async def test_insert_then_unchanged_does_not_move_updated_at(platform, tenant) -> None:
    ctx = await ctx_for(platform, tenant)
    r1 = await apply(platform, tenant, ctx, [finding(1), finding(2)])
    assert (r1.added, r1.updated, r1.unchanged) == (2, 0, 0)
    a = await row(platform, tenant, ctx, "f:1")
    r2 = await apply(platform, tenant, ctx, [finding(1), finding(2)])
    assert (r2.added, r2.updated, r2.unchanged) == (0, 0, 2)
    b = await row(platform, tenant, ctx, "f:1")
    assert a["updated_at"] == b["updated_at"]
    assert b["last_seen_at"] > a["last_seen_at"]
    # A material change moves updated_at.
    r3 = await apply(platform, tenant, ctx, [finding(1, title="changed")])
    assert r3.updated == 1
    c = await row(platform, tenant, ctx, "f:1")
    assert c["updated_at"] > b["updated_at"] and c["first_seen_at"] == a["first_seen_at"]


async def test_reopened_is_derived_and_sticky(platform, tenant) -> None:
    ctx = await ctx_for(platform, tenant)
    await apply(platform, tenant, ctx, [finding(1)])
    await apply(
        platform,
        tenant,
        ctx,
        [finding(1, FindingState.CLOSED, state_changed_at=datetime(2026, 1, 2, tzinfo=UTC))],
    )
    closed = await row(platform, tenant, ctx, "f:1")
    assert closed["state"] == "CLOSED"
    assert closed["state_updated_at"] == datetime(
        2026, 1, 2, tzinfo=UTC
    )  # the vendor's timestamp (NORM-05)
    await apply(platform, tenant, ctx, [finding(1)])
    assert (await row(platform, tenant, ctx, "f:1"))["state"] == "REOPENED"
    r = await apply(platform, tenant, ctx, [finding(1)])
    assert r.unchanged == 1 and (await row(platform, tenant, ctx, "f:1"))["state"] == "REOPENED"
    await apply(platform, tenant, ctx, [finding(1, FindingState.IGNORED)])
    assert (await row(platform, tenant, ctx, "f:1"))["state"] == "IGNORED"
    h = await history(platform, tenant, ctx, closed["id"])
    assert [(x["from_state"], x["to_state"]) for x in h] == [
        (None, "OPEN"),
        ("OPEN", "CLOSED"),
        ("CLOSED", "REOPENED"),
        ("REOPENED", "IGNORED"),
    ]


async def test_tombstone_and_undelete(platform, tenant) -> None:
    ctx = await ctx_for(platform, tenant)
    await apply(platform, tenant, ctx, [finding(1, FindingState.CLOSED)])
    r = await apply(platform, tenant, ctx, [Tombstone("vulnerability_finding", "f:1")])
    assert r.deleted == 1
    gone = await row(platform, tenant, ctx, "f:1")
    assert gone["state"] == "DELETED" and gone["deleted_at"] is not None
    # Reappears open after being CLOSED before deletion: REOPENED (STORE-04).
    r = await apply(platform, tenant, ctx, [finding(1)])
    assert r.undeleted == 1
    back = await row(platform, tenant, ctx, "f:1")
    assert back["deleted_at"] is None and back["state"] == "REOPENED" and back["id"] == gone["id"]


async def test_stub_resources_and_links(platform, tenant) -> None:
    ctx = await ctx_for(platform, tenant)
    r = await apply(platform, tenant, ctx, [finding(1), finding(4)])  # both reference h:1
    assert r.stubs == 1
    stub = await row(platform, tenant, ctx, "h:1", "data.resource")
    assert stub["is_stub"] and stub["state"] == "UNKNOWN" and stub["stream"] == "hosts"
    rctx = BatchContext(
        ctx.environment_id, ctx.organization_id, ctx.connection_id, "hosts", "resource", "1.0.0"
    )
    r2 = await apply(platform, tenant, rctx, [host(1)])
    assert r2.updated == 1 and r2.added == 0
    filled = await row(platform, tenant, ctx, "h:1", "data.resource")
    assert not filled["is_stub"] and filled["id"] == stub["id"] and filled["state"] == "ACTIVE"
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        links = await fetch_all(
            conn,
            "select * from data.finding_resource where connection_id = %s",
            (ctx.connection_id,),
        )
        head = await fetch_required(
            conn,
            "select * from data.stream_head where connection_id = %s and stream = 'hosts'",
            (ctx.connection_id,),
        )
    assert len(links) == 2 and all(lnk["resource_id"] == stub["id"] for lnk in links)
    assert head["live_count"] == 1  # the stub counted once, filling it in did not double count


async def test_counts_are_exact(platform, tenant) -> None:
    ctx = await ctx_for(platform, tenant)
    await apply(platform, tenant, ctx, [finding(i) for i in range(10)])
    await apply(
        platform, tenant, ctx, [Tombstone("vulnerability_finding", f"f:{i}") for i in range(3)]
    )
    await apply(platform, tenant, ctx, [finding(1)])
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        head = await fetch_required(
            conn,
            "select * from data.stream_head where connection_id = %s and stream = 'findings'",
            (ctx.connection_id,),
        )
        actual = await fetch_required(
            conn,
            """select count(*) filter (where deleted_at is null) as live,
                                                 count(*) filter (where deleted_at is not null) as deleted
                                            from data.vulnerability_finding where connection_id = %s""",
            (ctx.connection_id,),
        )
    assert (
        (head["live_count"], head["deleted_count"]) == (actual["live"], actual["deleted"]) == (8, 2)
    )


async def test_quarantine_and_severity_floor(platform, tenant) -> None:
    ctx = await ctx_for(platform, tenant)
    floor_ctx = BatchContext(**{**ctx.__dict__, "severity_floor": Severity.HIGH})
    r = await apply(
        platform,
        tenant,
        floor_ctx,
        [
            finding(1, severity=Severity.LOW),
            finding(2),
            Invalid("f:bad", [{"msg": "bad"}]),
            finding(3, severity=Severity.UNKNOWN),
        ],
    )
    assert (r.added, r.filtered, r.quarantined) == (2, 1, 1)
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        q = await fetch_all(
            conn, "select * from data.quarantine where connection_id = %s", (ctx.connection_id,)
        )
    assert len(q) == 1 and q[0]["natural_key"] == "f:bad"


async def test_sweep_guard_and_cascade(platform, tenant) -> None:
    rctx = await ctx_for(platform, tenant, "resource", "hosts")
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        g1 = await records.new_generation(conn)
    rctx = BatchContext(**{**rctx.__dict__, "generation": g1})
    await apply(platform, tenant, rctx, [host(i) for i in range(30)])
    fctx = BatchContext(
        rctx.environment_id,
        rctx.organization_id,
        rctx.connection_id,
        "findings",
        "vulnerability_finding",
        "1.0.0",
    )
    await apply(
        platform, tenant, fctx, [finding(i) for i in range(6)]
    )  # primary resources h:0..h:2
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        g2 = await records.new_generation(conn)
    g2ctx = BatchContext(**{**rctx.__dict__, "generation": g2})
    # Second pass sees everything except h:1: a normal sweep that cascades to h:1's findings.
    await apply(platform, tenant, g2ctx, [host(i) for i in range(30) if i != 1])
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        res = await records.sweep(conn, g2ctx, g2)
    assert (res.deleted, res.aborted, res.cascaded) == (1, False, 2)
    # Third pass sees nothing: the guard aborts and deletes nothing.
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        g3 = await records.new_generation(conn)
        res = await records.sweep(conn, BatchContext(**{**rctx.__dict__, "generation": g3}), g3)
    assert res.aborted and res.deleted == 0 and res.would_delete == 29


async def test_concurrent_writers_never_hide_a_change_from_an_incremental_reader(
    platform, tenant
) -> None:
    """CDC-01: readers paging by (updated_at, id) see every row's final version."""
    ctx = await ctx_for(platform, tenant)
    keys = 60
    await apply(platform, tenant, ctx, [finding(i) for i in range(keys)])
    stop = asyncio.Event()
    rng = random.Random(1)  # noqa: S311

    async def writer(w: int) -> None:
        for batch in range(25):
            picks = rng.sample(range(keys), 8)
            await apply(platform, tenant, ctx, [finding(i, title=f"w{w}b{batch}") for i in picks])
            await asyncio.sleep(0)

    async def reader(seen: dict[Any, datetime]) -> None:
        pos: tuple[datetime, Any] | None = None
        while True:
            done = stop.is_set()
            async with tenant_tx(platform.pool, tenant.environment_id) as conn:
                if pos is None:
                    got = await fetch_all(
                        conn,
                        "select id, updated_at from data.vulnerability_finding where connection_id = %s "
                        "order by updated_at, id limit 25",
                        (ctx.connection_id,),
                    )
                else:
                    got = await fetch_all(
                        conn,
                        "select id, updated_at from data.vulnerability_finding where connection_id = %s "
                        "and (updated_at, id) > (%s, %s) order by updated_at, id limit 25",
                        (ctx.connection_id, pos[0], pos[1]),
                    )
            for g in got:
                seen[g["id"]] = max(seen.get(g["id"], g["updated_at"]), g["updated_at"])
            if got:
                pos = (got[-1]["updated_at"], got[-1]["id"])
            elif done:
                return
            await asyncio.sleep(0.001)

    views: list[dict[Any, datetime]] = [{} for _ in range(3)]
    readers = [asyncio.create_task(reader(v)) for v in views]
    await asyncio.gather(*(writer(w) for w in range(4)))
    stop.set()
    await asyncio.gather(*readers)
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        final = {
            r["id"]: r["updated_at"]
            for r in await fetch_all(
                conn,
                "select id, updated_at from data.vulnerability_finding where connection_id = %s",
                (ctx.connection_id,),
            )
        }
    for view in views:
        missed = [k for k, ts in final.items() if view.get(k) != ts]
        assert not missed, f"a reader skipped {len(missed)} change(s)"


async def test_vendor_payloads_are_encrypted_at_rest_when_keys_are_set(
    database_url, tenant
) -> None:
    import base64
    import os

    from securefabric_core.crypto import VaultError
    from securefabric_domain.records import decode_vendor_data, payload_binding
    from securefabric_domain.testing import (
        build_test_platform,
        build_test_settings,
        make_connection,
        sync_stream,
    )
    from securefabric_schema import Mode

    key = base64.b64encode(os.urandom(32)).decode()
    p = build_test_platform(database_url, settings=build_test_settings(payload_keys=f"1:{key}"))
    await p.open()
    try:
        assert p.payload is not None
        cid = await make_connection(p, tenant, credentials={"api_key": "sbx_store09_k"})
        out = await sync_stream(p, tenant, cid, "findings", Mode.BACKFILL)
        assert out.kind == "completed", out.error
        async with tenant_tx(p.pool, tenant.environment_id) as conn:
            rows = await fetch_all(
                conn,
                "select vendor_data from data.vulnerability_finding where connection_id = %s",
                (cid,),
            )
        blobs = [bytes(r["vendor_data"]) for r in rows if r["vendor_data"]]
        assert blobs and all(b[0] == 0x02 for b in blobs)  # sealed format
        bound = payload_binding(tenant.environment_id, cid, "vulnerability_finding")
        decoded = decode_vendor_data(blobs[0], cipher=p.payload, bound_to=bound)
        assert isinstance(decoded, dict) and decoded
        with pytest.raises(VaultError):  # another connection's binding: refused
            decode_vendor_data(
                blobs[0],
                cipher=p.payload,
                bound_to=payload_binding(tenant.environment_id, tenant.environment_id, "x"),
            )
        with pytest.raises(ValueError, match="no payload key"):
            decode_vendor_data(blobs[0])
    finally:
        await p.close()


async def test_payload_key_rotation_drill(database_url, platform, tenant) -> None:
    """Plaintext rows → turn encryption on → rotate to a new key → drop the old key."""
    import base64
    import os

    from securefabric_domain.maintenance import payload_reencrypt
    from securefabric_domain.records import decode_vendor_data, payload_binding
    from securefabric_domain.testing import (
        build_test_platform,
        build_test_settings,
        make_connection,
        sync_stream,
    )
    from securefabric_schema import Mode

    k1, k2 = (base64.b64encode(os.urandom(32)).decode() for _ in range(2))

    async def with_keys(keys: str | None) -> Any:
        p = build_test_platform(database_url, settings=build_test_settings(payload_keys=keys))
        await p.open()
        return p

    async def formats(cid: Any) -> set[tuple[int, int | None]]:
        async with tenant_tx(platform.pool, tenant.environment_id) as conn:
            rows = await fetch_all(
                conn,
                """select get_byte(vendor_data, 0) as f,
                          case when get_byte(vendor_data, 0) = 2 then get_byte(vendor_data, 1) end as v
                     from data.vulnerability_finding where connection_id = %s and vendor_data is not null""",
                (cid,),
            )
        return {(r["f"], r["v"]) for r in rows}

    # 1. Written before any key: plaintext (format 1).
    cid = await make_connection(platform, tenant, credentials={"api_key": "sbx_rotation_drill"})
    assert (await sync_stream(platform, tenant, cid, "findings", Mode.BACKFILL)).kind == "completed"
    assert await formats(cid) == {(1, None)}

    # 2. Turn encryption on (key 1): the job seals existing rows.
    p1 = await with_keys(f"1:{k1}")
    try:
        res = await payload_reencrypt(p1, connection_id=str(cid))
        assert res["reencrypted"] > 0 and res["remaining"] == 0 and res["unreadable"] == 0
    finally:
        await p1.close()
    assert await formats(cid) == {(2, 1)}

    # 3. Rotate: add key 2; the job re-seals everything with it.
    p12 = await with_keys(f"1:{k1},2:{k2}")
    try:
        assert (await payload_reencrypt(p12, connection_id=str(cid)))["remaining"] == 0
    finally:
        await p12.close()
    assert await formats(cid) == {(2, 2)}

    # 4. Drop key 1: every row still opens with key 2 alone.
    p2 = await with_keys(f"2:{k2}")
    try:
        bound = payload_binding(tenant.environment_id, cid, "vulnerability_finding")
        async with tenant_tx(p2.pool, tenant.environment_id) as conn:
            blobs = await fetch_all(
                conn,
                "select vendor_data from data.vulnerability_finding where connection_id = %s",
                (cid,),
            )
        assert all(
            decode_vendor_data(b["vendor_data"], cipher=p2.payload, bound_to=bound) for b in blobs
        )
        # The record itself did not change: re-encryption is invisible to the change feed.
        async with tenant_tx(p2.pool, tenant.environment_id) as conn:
            changed = await fetch_all(
                conn,
                "select 1 from data.vulnerability_finding where connection_id = %s "
                "and updated_at > created_at",
                (cid,),
            )
        assert changed == []
    finally:
        await p2.close()


async def test_reencryption_skips_and_alerts_on_rows_it_cannot_open(database_url, tenant) -> None:
    import base64
    import os

    from securefabric_domain.maintenance import payload_reencrypt
    from securefabric_domain.testing import (
        build_test_platform,
        build_test_settings,
        make_connection,
        sync_stream,
    )
    from securefabric_schema import Mode

    def key() -> str:
        return base64.b64encode(os.urandom(32)).decode()

    lost = build_test_platform(
        database_url, settings=build_test_settings(payload_keys=f"1:{key()}")
    )
    await lost.open()
    try:
        cid = await make_connection(lost, tenant, credentials={"api_key": "sbx_lost_key_1"})
        assert (await sync_stream(lost, tenant, cid, "findings", Mode.BACKFILL)).kind == "completed"
    finally:
        await lost.close()
    # A different key under the same version number (the original is gone), now at v2.
    p = build_test_platform(
        database_url, settings=build_test_settings(payload_keys=f"1:{key()},2:{key()}")
    )
    await p.open()
    try:
        res = await payload_reencrypt(p, connection_id=str(cid))  # finishes, does not stall
        assert res["reencrypted"] == 0 and res["unreadable"] > 0 and res["remaining"] == 0
        async with tenant_tx(p.sys_pool, tenant.environment_id) as conn:
            alert = await fetch_required(
                conn,
                "select detail from obs.alert where name = 'payload_unreadable' "
                "and resolved_at is null order by raised_at desc limit 1",
            )
        assert alert["detail"]["loaded_versions"] == [1, 2]
    finally:
        await p.close()
