"""The audit log reads in pages, filters exactly, and never crosses environments."""

from dataclasses import replace

import pytest

from securefabric_core import BadRequestError
from securefabric_db import tenant_tx
from securefabric_domain import audit_log, tenancy
from securefabric_domain.testing import build_test_platform, build_test_settings, make_tenant


async def test_pages_filters_facets_and_isolation(database_url: str) -> None:
    api = build_test_platform(database_url, role="api", settings=build_test_settings())
    worker = build_test_platform(database_url, role="test")
    await api.open()
    await worker.open()
    try:
        tenant = await make_tenant(worker)
        user = replace(
            tenancy.system_principal(tenant.environment_id, tenant.account_id),
            kind="user",
            role="admin",
            actor_id="user-1",
        )
        key = replace(user, kind="api_key", actor_id="key-1")
        async with tenant_tx(worker.pool, tenant.environment_id) as conn:
            for i in range(25):
                await tenancy.audit(
                    conn, user, "connection.created", target_kind="connection", target_id=f"c{i}"
                )
            for i in range(5):
                await tenancy.audit(
                    conn, key, "api_key.revoked", target_kind="api_key", target_id=f"k{i}"
                )
        async with tenant_tx(worker.pool, tenant.other_environment_id) as conn:
            other = replace(user, environment_id=tenant.other_environment_id)
            await tenancy.audit(conn, other, "connection.created", target_id="elsewhere")

        seen: list[str] = []
        cursor = None
        while True:
            page = await audit_log.list_events(api, user, cursor=cursor, limit=7)
            seen.extend(str(r["id"]) for r in page.items)
            if not page.next_cursor:
                break
            cursor = page.next_cursor
        assert len(seen) == len(set(seen)) == 30

        only_keys = await audit_log.list_events(api, user, actor_kind=["api_key"], limit=100)
        assert {r["action"] for r in only_keys.items} == {"api_key.revoked"}
        assert len(only_keys.items) == 5

        found = await audit_log.list_events(api, user, search="c1", limit=100)
        # c1 and c10..c19
        assert {r["target_id"] for r in found.items} == {"c1", *(f"c{i}" for i in range(10, 20))}

        with pytest.raises(BadRequestError):
            await audit_log.list_events(
                api, user, actor_kind=["user"], cursor=only_keys.next_cursor or cursor, limit=7
            )

        facets = await audit_log.facets(api, user)
        assert facets["total"] == 30
        assert {f["value"]: f["count"] for f in facets["action"]} == {
            "connection.created": 25,
            "api_key.revoked": 5,
        }
        assert sum(b["count"] for b in facets["histogram"]) == 30
    finally:
        await api.close()
        await worker.close()
