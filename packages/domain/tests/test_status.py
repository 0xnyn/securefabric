"""System status facts: collected under the least-privileged role, redacted by audience."""

from typing import Any

from securefabric_domain import status
from securefabric_domain.runtime import Platform
from securefabric_domain.sync.scheduler import raise_alert
from securefabric_domain.testing import build_test_platform, build_test_settings


async def _facts(platform: Platform) -> dict[str, Any]:
    async with platform.pool.connection() as conn:
        return await status.collect(conn, version="t")


async def test_collect_works_as_sf_api_and_views_redact(database_url: str) -> None:
    api = build_test_platform(database_url, role="api", settings=build_test_settings())
    worker = build_test_platform(database_url, role="test")
    await api.open()
    await worker.open()
    try:
        async with worker.sys_pool.connection() as conn, conn.transaction():
            await conn.execute(
                """insert into obs.worker_heartbeat (worker_id, role, queues, hostname, pid, version,
                                                     concurrency, started_at, last_seen_at)
                   values ('status-test', 'sync', '{sync_bulk}', 'host-secret', 4242, 't', 2, now(), now())
                   on conflict (worker_id) do update set last_seen_at = now()"""
            )
            await raise_alert(
                conn, "status_test_alert", "run-in-another-tenant", {}, severity="page"
            )
        facts = await _facts(api)
        assert facts["database"]["reachable"] and facts["migrations"]["applied"]
        assert facts["migrations"]["compared_with_disk"] and not facts["migrations"]["unknown"]
        assert any(w["hostname"] == "host-secret" for w in facts["workers"])
        assert facts["alert_counts"].get("page", 0) >= 1
        assert facts["status"] == "degraded" and any("paging" in p for p in facts["problems"])

        operator = status.view(facts, "operator")
        assert any(a["subject"] == "run-in-another-tenant" for a in operator["alerts"])

        customer = status.view(facts, "customer")
        blob = repr(customer)
        assert "host-secret" not in blob and "4242" not in blob
        assert "run-in-another-tenant" not in blob and customer["alerts"] == []
        assert customer["alert_counts"] == facts["alert_counts"]

        public = status.view(facts, "public")
        assert public["database"] == {"reachable": True} and public["workers"] == []
        assert public["status"] == facts["status"] and public["problems"] == []
    finally:
        async with worker.sys_pool.connection() as conn, conn.transaction():
            await conn.execute("delete from obs.worker_heartbeat where worker_id = 'status-test'")
            await conn.execute("delete from obs.alert where name = 'status_test_alert'")
        await api.close()
        await worker.close()


def test_down_is_reported_not_raised() -> None:
    facts = status.down("t", ConnectionRefusedError())
    assert facts["status"] == "down" and facts["database"] == {
        "reachable": False,
        "error": "ConnectionRefusedError",
    }
    assert status.view(facts, "public")["status"] == "down"
