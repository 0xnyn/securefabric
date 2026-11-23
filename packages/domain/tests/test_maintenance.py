"""Maintenance jobs: partitions, retention, purge, abandoned, alerts, usage rollup."""

from datetime import timedelta

import pytest

from securefabric_db import fetch_all, fetch_required, system_tx, tenant_tx
from securefabric_domain import maintenance
from securefabric_domain.testing import make_connection, rows, sync_stream
from securefabric_schema import Mode

pytestmark = pytest.mark.integration


async def test_partitions_are_created_ahead(platform) -> None:
    platform.clock.set(platform.clock.now().replace(year=2030, month=6, day=1))
    res = await maintenance.partitions(platform)
    assert res["created"] > 0
    async with system_tx(platform.sys_pool) as conn:
        assert (
            await fetch_required(conn, "select to_regclass('obs.operation_p20300608') as t")
            is not None
        )
        found = await fetch_required(conn, "select to_regclass('obs.operation_p20300608') as t")
    assert found["t"] is not None
    assert (await maintenance.partitions(platform))["created"] == 0  # idempotent


async def test_retention_drops_old_partitions_and_rows(platform) -> None:
    platform.clock.set(platform.clock.now().replace(year=2031, month=1, day=1))
    await maintenance.partitions(platform)
    platform.clock.set(platform.clock.now().replace(year=2031, month=3, day=15))
    res = await maintenance.retention(platform)
    assert res["dropped_partitions"] > 0
    async with system_tx(platform.sys_pool) as conn:
        assert (await fetch_required(conn, "select to_regclass('obs.operation_p20310101') as t"))[
            "t"
        ] is None


async def test_purge_hard_deletes_after_30_days(platform, tenant) -> None:
    from securefabric_domain.connections import delete_connection
    from securefabric_domain.tenancy import system_principal

    cid = await make_connection(
        platform, tenant, credentials={"api_key": "sbx_purge_key"}, options={"finding_count": 5}
    )
    await sync_stream(platform, tenant, cid, "findings", Mode.BACKFILL)
    await delete_connection(
        platform, system_principal(tenant.environment_id, tenant.account_id), cid
    )
    assert len(await rows(platform, tenant, cid)) == 5  # data outlives the delete until purge
    assert (await maintenance.purge(platform))["purged"] == 0
    platform.clock.advance(days=31)
    assert (await maintenance.purge(platform))["purged"] >= 1
    assert await rows(platform, tenant, cid) == []
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        assert (
            await fetch_required(conn, "select state from control.connection where id = %s", (cid,))
        )["state"] == "HARD_DELETED"


async def test_abandoned_pending_connections(platform, tenant) -> None:
    cid = await make_connection(
        platform, tenant, state="PENDING", credentials={"api_key": "sbx_pend_key"}
    )
    platform.clock.advance(days=8)
    async with system_tx(platform.sys_pool) as conn:
        await conn.execute(
            "update control.connection set created_at = %s where id = %s",
            (platform.clock.now() - timedelta(days=8), cid),
        )
    await maintenance.abandoned(platform)
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        assert (
            await fetch_required(conn, "select state from control.connection where id = %s", (cid,))
        )["state"] == "DELETED"


async def test_freshness_alert_and_usage_rollup(platform, tenant) -> None:
    cid = await make_connection(platform, tenant, credentials={"api_key": "sbx_fresh_key"})
    async with system_tx(platform.sys_pool) as conn:
        await conn.execute(
            "update control.connection set health_status = 'HEALTHY', health_code = 'HEALTHY' where id = %s",
            (cid,),
        )
        await conn.execute(
            """insert into sync.stream_schedule (environment_id, connection_id, stream, interval_s, next_run_at,
              last_success_at)
               values (%s, %s, 'findings', 3600, now(), now() - interval '3 hours')""",
            (tenant.environment_id, cid),
        )
    await maintenance.alerts(platform)
    async with system_tx(platform.sys_pool) as conn:
        alert = await fetch_required(
            conn,
            "select * from obs.alert where name = 'freshness_breach' and subject = %s",
            (f"{cid}/findings",),
        )
    assert alert is not None and alert["runbook"] == "docs/runbooks/freshness_breach.md"
    await maintenance.usage_rollup(platform)
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        rows_ = await fetch_all(
            conn,
            "select * from obs.usage_daily where environment_id = %s",
            (tenant.environment_id,),
        )
    assert rows_ and rows_[0]["active_connections"] == 0  # SANDBOX never counts toward billing


async def test_alerts_resolve_when_their_condition_clears(platform) -> None:
    from securefabric_domain.sync.scheduler import raise_alert

    async with system_tx(platform.sys_pool) as conn:
        await conn.execute("update obs.alert set resolved_at = now() where resolved_at is null")
        await raise_alert(conn, "freshness_breach", "00000000-0000-0000-0000-000000000000/x", {})
        await raise_alert(conn, "connector_failure_rate", "NOT_FAILING", {})
        await raise_alert(conn, "admission_lag", None, {})
        await raise_alert(conn, "admission_lag", "run 123", {})  # a one-off event
        await raise_alert(conn, "internal_error", "run 456", {})  # not condition-based
    res = await maintenance.alerts(platform)
    assert res["resolved"] >= 3
    mine = {
        ("freshness_breach", "00000000-0000-0000-0000-000000000000/x"),
        ("connector_failure_rate", "NOT_FAILING"),
        ("admission_lag", None),
        ("admission_lag", "run 123"),
        ("internal_error", "run 456"),
    }
    async with system_tx(platform.sys_pool) as conn:
        # (Other tests' connections in this database may genuinely be stale and alert.)
        still_open = {
            (a["name"], a["subject"])
            for a in await fetch_all(
                conn, "select name, subject from obs.alert where resolved_at is null"
            )
        } & mine
        auto = await fetch_required(
            conn,
            "select detail from obs.alert where name = 'connector_failure_rate' "
            "and subject = 'NOT_FAILING'",
        )
    assert still_open == {("admission_lag", "run 123"), ("internal_error", "run 456")}
    assert auto["detail"]["resolution"]["by"] == "auto"


async def test_operators_resolve_alerts_with_a_note(platform) -> None:
    from dataclasses import replace

    from securefabric_core import PermissionDeniedError
    from securefabric_domain.ops import resolve_alert
    from securefabric_domain.sync.scheduler import raise_alert
    from securefabric_domain.tenancy import Principal

    async with system_tx(platform.sys_pool) as conn:
        await raise_alert(conn, "sweep_aborted", "conn/stream", {})
        alert = await fetch_required(
            conn,
            "select id from obs.alert where name = 'sweep_aborted' and resolved_at is null",
        )
    customer = Principal(
        kind="api_key", account_id=None, environment_id=None, scopes=frozenset(), actor_id="k1"
    )
    with pytest.raises(PermissionDeniedError):
        await resolve_alert(platform, customer, alert["id"], "nope")
    operator = replace(customer, kind="user", actor_id="u1", is_operator=True)
    row = await resolve_alert(platform, operator, alert["id"], "vendor confirmed the deletion")
    assert row["resolved_at"] is not None
    assert row["detail"]["resolution"] == {"by": "user:u1", "note": "vendor confirmed the deletion"}
