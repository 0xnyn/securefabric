"""Passthrough (RAW-01), re-normalisation (STORE-11) and the operator console (OPS-01/05/08, RAW-02)."""

import asyncio
from dataclasses import replace

import pytest

from securefabric_core import BadRequestError, PermissionDeniedError, ValidationFailedError
from securefabric_db import fetch_all, fetch_one, tenant_tx
from securefabric_domain import operator, passthrough
from securefabric_domain.renormalize import renormalize
from securefabric_domain.tenancy import ALL_SCOPES, Principal, system_principal
from securefabric_domain.testing import make_connection, run_control, sync_stream
from securefabric_schema import Mode

pytestmark = pytest.mark.integration

OPERATOR = Principal(
    kind="user",
    account_id=None,
    environment_id=None,
    scopes=ALL_SCOPES,
    actor_id="op-1",
    is_operator=True,
    extra={"email": "ops@securefabric.dev"},
)


async def test_passthrough_is_allowlisted_and_runs_in_the_worker(platform, tenant) -> None:
    cid = await make_connection(platform, tenant, credentials={"api_key": "sbx_passthru_key"})
    p = system_principal(tenant.environment_id, tenant.account_id)
    with pytest.raises(ValidationFailedError):
        await passthrough.request(platform, p, cid, method="GET", path="/v1/findings", query=None)
    with pytest.raises(ValidationFailedError):
        await passthrough.request(platform, p, cid, method="DELETE", path="/v1/me", query=None)
    pending = asyncio.create_task(
        passthrough.request(platform, p, cid, method="GET", path="/v1/me", query=None, wait_s=10)
    )
    await asyncio.sleep(0.3)
    await run_control(platform)
    res = await pending
    assert res["status"] == 200 and res["body"]["tenant_id"].startswith("t_")
    assert "sbx_passthru_key" not in str(res)


async def test_renormalisation_replays_the_archive_without_vendor_calls(platform, tenant) -> None:
    cid = await make_connection(
        platform, tenant, credentials={"api_key": "sbx_renorm_key"}, options={"finding_count": 30}
    )
    await sync_stream(platform, tenant, cid, "findings", Mode.BACKFILL)
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        await conn.execute(
            "update data.vulnerability_finding set title = 'corrupted', hash = '\\x00' where connection_id = %s",
            (cid,),
        )
    res = await renormalize(platform, tenant.environment_id, cid, "findings")
    assert res["pages"] >= 1 and res["updated"] == 30
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        titles = {
            r["title"]
            for r in await fetch_all(
                conn,
                "select title from data.vulnerability_finding where connection_id = %s",
                (cid,),
            )
        }
    assert "corrupted" not in titles


async def test_operator_console(platform, tenant) -> None:
    cid = await make_connection(
        platform, tenant, credentials={"api_key": "sbx_operator_key"}, options={"finding_count": 8}
    )
    await sync_stream(platform, tenant, cid, "findings", Mode.BACKFILL)
    with pytest.raises(PermissionDeniedError):
        await operator.search(platform, replace(OPERATOR, is_operator=False), str(cid))
    hits = await operator.search(platform, OPERATOR, str(cid))
    assert [h["connection_id"] for h in hits] == [cid]
    assert isinstance(await operator.scheduler_view(platform, OPERATOR), list)
    with pytest.raises(BadRequestError):
        await operator.repair(
            platform, OPERATOR, tenant.environment_id, cid, "rebuild_counts", None
        )
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        await conn.execute(
            "update data.stream_head set live_count = 999 where connection_id = %s", (cid,)
        )
    res = await operator.repair(
        platform, OPERATOR, tenant.environment_id, cid, "rebuild_counts", "count drift ticket #42"
    )
    assert {s["stream"]: s["live_count"] for s in res["streams"]}["findings"] == 8
    pages = await operator.raw_pages(
        platform,
        OPERATOR,
        tenant.environment_id,
        "customer asked about a finding",
        connection_id=cid,
        run_id=None,
    )
    assert pages
    viewing = asyncio.create_task(
        operator.view_raw_page(
            platform,
            OPERATOR,
            tenant.environment_id,
            pages[0]["id"],
            "customer asked about a finding",
        )
    )
    await asyncio.sleep(0.3)
    await run_control(platform)
    page = await viewing
    assert "items" in page["body"] and "sbx_operator_key" not in page["body"]
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        audits = await fetch_all(
            conn,
            "select actor_kind, action, detail from obs.audit_event where actor_id = 'op-1' order by at",
        )
    assert {a["action"] for a in audits} >= {
        "support.access",
        "support.rebuild_counts",
        "support.raw_page_viewed",
    }
    assert all(a["actor_kind"] == "support" for a in audits)
    _ = fetch_one


async def test_queued_repairs_are_validated_up_front_and_can_be_followed(platform, tenant) -> None:
    cid = await make_connection(platform, tenant, credentials={"api_key": "sbx_repair_follow"})
    why = "ticket 77: rebuild from the archive"
    # A renormalize without a valid stream is refused, never queued to fail in the worker.
    for params in ({}, {"stream": "no_such_stream"}):
        with pytest.raises(ValidationFailedError) as exc:
            await operator.repair(
                platform, OPERATOR, tenant.environment_id, cid, "renormalize", why, params
            )
        assert exc.value.error_code == "stream_required"
    queued = await operator.repair(
        platform, OPERATOR, tenant.environment_id, cid, "reprobe", why, {}
    )
    task_id = queued["task_id"]
    before = await operator.repair_status(platform, OPERATOR, task_id)
    assert before["state"] == "pending" and before["failure"] is None
    await run_control(platform)
    after = await operator.repair_status(platform, OPERATOR, task_id)
    assert after["state"] == "completed", after
    with pytest.raises(PermissionDeniedError):
        await operator.repair_status(platform, replace(OPERATOR, is_operator=False), task_id)
