import pytest

from securefabric_domain.testing import make_connection, rows, sync_stream
from securefabric_schema import Mode

pytestmark = pytest.mark.integration


async def test_sandbox_streams_sync_through_the_real_write_path(platform, tenant) -> None:
    cid = await make_connection(
        platform,
        tenant,
        credentials={"api_key": "sbx_smoke_key"},
        options={"finding_count": 40, "host_count": 9, "image_count": 4, "page_size": 7},
    )
    for stream in ("hosts", "images"):
        out = await sync_stream(platform, tenant, cid, stream, Mode.FULL)
        assert out.kind == "completed", out.error
    out = await sync_stream(platform, tenant, cid, "findings", Mode.BACKFILL)
    assert out.kind == "completed", out.error
    assert out.counts.added == 40
    findings = await rows(platform, tenant, cid)
    assert len(findings) == 40
    resources = await rows(platform, tenant, cid, "data.resource")
    assert {r["type"] for r in resources} == {"HOST", "IMAGE", "CONTAINER"}
    assert not any(r["is_stub"] for r in resources)


async def test_an_object_store_outage_does_not_stop_a_sync(platform, tenant) -> None:
    class Broken:
        async def put(self, key, data):
            raise RuntimeError("RequestTimeTooSkewed")

    platform.blob = Broken()
    cid = await make_connection(
        platform, tenant, credentials={"api_key": "sbx_outage_key"}, options={"finding_count": 12}
    )
    out = await sync_stream(platform, tenant, cid, "findings", Mode.BACKFILL)
    assert out.kind == "completed" and out.counts.added == 12
