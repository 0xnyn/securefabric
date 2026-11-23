"""SYNC-16: async export with polling (parked between polls), chunked download,
resume after a worker dies mid-download, and an expired export re-requested."""

from datetime import timedelta

import pytest

from securefabric_db import fetch_required, tenant_tx
from securefabric_domain.sync import jobs
from securefabric_domain.sync.bundle import budget_key_for
from securefabric_domain.testing import EngineDriver, make_connection, rows, sync_stream
from securefabric_schema import Mode

pytestmark = pytest.mark.integration


async def test_export_parks_while_preparing_then_downloads(platform, tenant) -> None:
    cid = await make_connection(
        platform, tenant, credentials={"api_key": "sbx_export_key"}, options={"finding_count": 1800}
    )
    first = await sync_stream(platform, tenant, cid, "finding_exports", Mode.FULL)
    assert first.kind == "parked" and first.reset_at - platform.clock.now() >= timedelta(seconds=29)
    done = await sync_stream(
        platform, tenant, cid, "finding_exports", Mode.FULL, generation=first.generation
    )
    assert done.kind == "completed", done.error
    assert done.counts.added == 1800 and done.pages == 4  # four 500-record chunks
    assert len(await rows(platform, tenant, cid)) == 1800


async def test_export_resumes_with_unfinished_chunks_after_a_kill(platform, tenant) -> None:
    cid = await make_connection(
        platform,
        tenant,
        credentials={"api_key": "sbx_export_kill"},
        options={"finding_count": 2600},
    )
    first = await sync_stream(platform, tenant, cid, "finding_exports", Mode.FULL)
    gen = first.generation
    killed = await sync_stream(
        platform, tenant, cid, "finding_exports", Mode.FULL, generation=gen, max_pages=2
    )
    assert killed.kind == "killed" and len(await rows(platform, tenant, cid)) == 1000
    resumed = await sync_stream(platform, tenant, cid, "finding_exports", Mode.FULL, generation=gen)
    assert (
        resumed.kind == "completed" and resumed.pages == 4
    )  # only the 4 chunks it had not finished
    assert len(await rows(platform, tenant, cid)) == 2600
    from securefabric_connectors.sandbox.vendor import vendor_for

    assert (
        len(vendor_for("sbx_export_kill", {"finding_count": 2600}).exports) == 1
    )  # the same export, not a new one


async def test_expired_export_is_requested_again(platform, tenant) -> None:
    cid = await make_connection(
        platform,
        tenant,
        credentials={"api_key": "sbx_export_exp"},
        options={"finding_count": 300, "scenario": "expire_export"},
    )
    first = await sync_stream(platform, tenant, cid, "finding_exports", Mode.FULL)
    second = await sync_stream(
        platform, tenant, cid, "finding_exports", Mode.FULL, generation=first.generation
    )
    while second.kind == "parked":
        second = await sync_stream(
            platform, tenant, cid, "finding_exports", Mode.FULL, generation=first.generation
        )
    assert second.kind == "completed" and len(await rows(platform, tenant, cid)) == 300


async def test_export_through_the_engine(platform, tenant) -> None:
    cid = await make_connection(
        platform, tenant, credentials={"api_key": "sbx_export_eng"}, options={"finding_count": 700}
    )
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        key = await budget_key_for(platform, conn, cid)
        job = await jobs.on_demand(
            platform,
            conn,
            cid,
            streams=["finding_exports"],
            force_full_refresh=True,
            since=None,
            requested_by="t",
            budget_key=key,
        )
    drv = EngineDriver(platform)
    await drv.step()
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        run = await fetch_required(
            conn, "select state, not_before from sync.stream_run where job_id = %s", (job,)
        )
    assert run["state"] == "PARKED"
    platform.clock.advance(seconds=40)
    await drv.drain()
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        run = await fetch_required(
            conn, "select state, added from sync.stream_run where job_id = %s", (job,)
        )
    assert run["state"] == "SUCCEEDED" and run["added"] == 700
