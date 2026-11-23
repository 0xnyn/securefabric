"""Engine scenarios (M3 exit): admission, parking, retries, fairness, refresh,
on-demand, cancellation and crash recovery, through scheduler + Absurd + handler."""

import asyncio
import uuid
from datetime import timedelta

import pytest

from securefabric_cdk.tokens import CachedToken, ExchangeProvider
from securefabric_db import fetch_all, fetch_required, system_tx, tenant_tx
from securefabric_domain.sync import jobs
from securefabric_domain.sync.bundle import budget_key_for
from securefabric_domain.sync.credentials import DbCredentialStore
from securefabric_domain.testing import EngineDriver, make_connection, rows

pytestmark = pytest.mark.integration


async def connection(platform, tenant, **opts):
    options = {"finding_count": 30, "host_count": 12, "image_count": 6, "page_size": 10, **opts}
    return await make_connection(
        platform, tenant, credentials={"api_key": f"sbx_{uuid.uuid4().hex[:10]}"}, options=options
    )


async def demand(platform, tenant, cid, streams=None, **kw):
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        key = await budget_key_for(platform, conn, cid)
        return await jobs.on_demand(
            platform,
            conn,
            cid,
            streams=streams,
            force_full_refresh=kw.get("full", False),
            since=None,
            requested_by="test",
            budget_key=key,
        )


async def runs(platform, tenant, job_id):
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        return {
            r["stream"]: r
            for r in await fetch_all(
                conn, "select * from sync.stream_run where job_id = %s", (job_id,)
            )
        }


async def job(platform, tenant, job_id):
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        return await fetch_required(conn, "select * from sync.job where id = %s", (job_id,))


async def test_on_demand_job_runs_to_success_and_emits_events(platform, tenant) -> None:
    cid = await connection(platform, tenant)
    job_id = await demand(platform, tenant, cid)
    drv = EngineDriver(platform)
    await drv.drain()
    assert {r["state"] for r in (await runs(platform, tenant, job_id)).values()} == {"SUCCEEDED"}
    j = await job(platform, tenant, job_id)
    assert j["status"] == "SUCCESS"
    assert len(await rows(platform, tenant, cid)) == 30
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        events = [
            e["type"]
            for e in await fetch_all(
                conn,
                "select type from events.outbox_event where connection_id = %s order by sequence",
                (cid,),
            )
        ]
        c = await fetch_required(
            conn, "select health_code from control.connection where id = %s", (cid,)
        )
        ops = await fetch_all(
            conn, "select status from obs.operation where connection_id = %s", (cid,)
        )
    assert "sync.completed" in events and "connection.sync.succeeded" in events
    assert "connection.health.changed" in events and c["health_code"] == "HEALTHY"
    assert len(ops) == 3 and {o["status"] for o in ops} == {"success"}


async def test_two_quick_on_demand_calls_return_the_same_job(platform, tenant) -> None:
    cid = await connection(platform, tenant)
    a = await demand(platform, tenant, cid)
    b = await demand(platform, tenant, cid)
    assert a == b


async def test_rate_limit_parks_frees_the_worker_and_resumes(platform, tenant) -> None:
    cid = await connection(platform, tenant, scenario="rate_limit_20m")
    job_id = await demand(platform, tenant, cid, ["findings"])
    drv = EngineDriver(platform)
    await drv.step()
    run = (await runs(platform, tenant, job_id))["findings"]
    assert run["state"] == "PARKED"
    assert run["not_before"] - platform.clock.now() >= timedelta(minutes=19)
    # A parked run holds no worker and no admission slot.
    assert await drv.step() == 0
    platform.clock.advance(minutes=21)
    await drv.drain()
    run = (await runs(platform, tenant, job_id))["findings"]
    assert run["state"] == "SUCCEEDED" and run["attempt"] == 1
    assert len(await rows(platform, tenant, cid)) == 30


async def test_vendor_500s_retry_on_schedule_then_fail(platform, tenant) -> None:
    cid = await connection(platform, tenant, scenario="server_errors")
    job_id = await demand(platform, tenant, cid, ["findings"])
    drv = EngineDriver(platform)
    expected = [60, 300, 900, 3600]
    for attempt, delay in enumerate(expected, start=1):
        await drv.step()
        run = (await runs(platform, tenant, job_id))["findings"]
        assert run["state"] == "RETRY_WAIT" and run["attempt"] == attempt + 1
        wait = (run["not_before"] - platform.clock.now()).total_seconds()
        assert 0.8 * delay - 30 <= wait <= 1.2 * delay + 1, (attempt, wait)
        platform.clock.set(run["not_before"] + timedelta(seconds=1))
    await drv.step()
    run = (await runs(platform, tenant, job_id))["findings"]
    assert run["state"] == "FAILED" and run["health_code"] == "VENDOR_SERVER_ERROR"
    assert (await job(platform, tenant, job_id))["status"] == "FAILED"


async def test_401_is_not_retried(platform, tenant) -> None:
    cid = await connection(platform, tenant, scenario="revoke_mid_run", finding_count=80)
    job_id = await demand(platform, tenant, cid, ["findings"])
    await EngineDriver(platform).drain()
    run = (await runs(platform, tenant, job_id))["findings"]
    assert run["state"] == "FAILED" and run["attempt"] == 1 and run["health_code"] == "UNAUTHORIZED"
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        c = await fetch_required(
            conn,
            "select health_code, resolution_owner from control.connection where id = %s",
            (cid,),
        )
        types = [
            e["type"]
            for e in await fetch_all(
                conn, "select type from events.outbox_event where connection_id = %s", (cid,)
            )
        ]
    assert c["health_code"] == "UNAUTHORIZED" and c["resolution_owner"] == "CUSTOMER"
    assert "connection.sync.unauthorized" in types


async def test_a_noisy_tenant_does_not_delay_another_tenants_on_demand_job(
    platform, tenant
) -> None:
    from securefabric_domain.testing import make_tenant

    other = await make_tenant(platform)
    noisy = [await connection(platform, tenant) for _ in range(4)]
    async with system_tx(platform.sys_pool) as conn:
        for i in range(500):
            cid = noisy[i % 4]
            c = await fetch_required(conn, "select * from control.connection where id = %s", (cid,))
            await conn.execute(
                """insert into sync.job (id, environment_id, connection_id, type) values (%s, %s, %s, 'SCHEDULED')""",
                (uuid.UUID(int=i + 1 + uuid.uuid4().int % 10**12), c["environment_id"], cid),
            )
            jid = (
                await fetch_required(
                    conn,
                    "select id from sync.job where connection_id = %s order by created_at desc limit 1",
                    (cid,),
                )
            )["id"]
            await conn.execute(
                """insert into sync.stream_run (job_id, environment_id, connection_id, stream, mode, priority, fair_key,
                                                budget_key, connector_id, queue, not_before)
                   values (%s, %s, %s, %s, 'full', 2, %s, %s, 'SANDBOX', 'sync_bulk', %s)""",
                (
                    jid,
                    c["environment_id"],
                    cid,
                    f"s{i}",
                    f"{c['environment_id']}/{c['organization_id']}",
                    f"budget-{i % 4}",
                    platform.clock.now() - timedelta(minutes=5),
                ),
            )
    quiet = await connection(platform, other)
    job_id = await demand(platform, other, quiet, ["findings"])
    drv = EngineDriver(platform)
    admitted = await drv.scheduler.admit()
    run = (await runs(platform, other, job_id))["findings"]
    assert run["state"] == "ADMITTED", "the on-demand run must be admitted in the first tick"
    async with system_tx(platform.sys_pool) as conn:
        noisy_running = (
            await fetch_required(
                conn,
                "select count(*) as n from sync.stream_run where environment_id = %s "
                "and state = 'ADMITTED'",
                (tenant.environment_id,),
            )
        )["n"]
    # Caps hold: 3 per connection x 4 connections, and per budget key (manifest: 8).
    assert noisy_running <= 12 and admitted >= 2
    async with system_tx(platform.sys_pool) as conn:  # leave no synthetic runs for other tests
        await conn.execute("delete from sync.job where connection_id = any(%s)", (noisy,))


async def test_fifty_concurrent_readers_cause_one_refresh_against_the_database(
    platform, tenant
) -> None:
    cid = await connection(platform, tenant)
    calls = {"n": 0}

    async def exchange(current):
        calls["n"] += 1
        await asyncio.sleep(0.02)
        return CachedToken(
            access_token=f"tok-{calls['n']}-{uuid.uuid4().hex}",
            expires_at=platform.clock.now() + timedelta(hours=1),
        )

    providers = [
        ExchangeProvider(
            DbCredentialStore(
                platform,
                environment_id=tenant.environment_id,
                connection_id=cid,
                clock=platform.clock,
            ),
            {"default": exchange},
            clock=platform.clock,
        )
        for _ in range(50)  # fifty independent readers, as if in different workers
    ]
    results = await asyncio.gather(*(p.material() for p in providers))
    assert calls["n"] == 1
    assert len({r.fingerprint for r in results}) == 1


async def test_cancel_stops_queued_and_running_work(platform, tenant) -> None:
    cid = await connection(platform, tenant)
    job_id = await demand(platform, tenant, cid)
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        await jobs.cancel_job(conn, job_id, platform.clock.now())
    await EngineDriver(platform).drain()
    assert {r["state"] for r in (await runs(platform, tenant, job_id)).values()} == {"CANCELLED"}
    assert (await job(platform, tenant, job_id))["status"] == "CANCELLED"


async def test_worker_death_resumes_from_the_checkpoint_without_an_attempt(
    platform, tenant
) -> None:
    from securefabric_domain.sync.executor import SliceInput, run_slice
    from securefabric_domain.sync.oplog import start_operation
    from securefabric_schema import Mode

    cid = await connection(platform, tenant, finding_count=60)
    job_id = await demand(platform, tenant, cid, ["hosts"], full=True)
    drv = EngineDriver(platform)
    await drv.scheduler.tick()
    [task] = await drv.claim("sync_interactive")
    run = (await runs(platform, tenant, job_id))["hosts"]
    # The worker runs one page, then dies: the run is RUNNING with a committed checkpoint.
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        await conn.execute(
            "update sync.stream_run set state = 'RUNNING', generation = 999999 where id = %s",
            (run["id"],),
        )
    op = await start_operation(
        platform.pool, environment_id=tenant.environment_id, kind="sync", action="t"
    )
    out = await run_slice(
        platform,
        SliceInput(
            tenant.environment_id,
            cid,
            "hosts",
            Mode.FULL,
            run_id=run["id"],
            generation=999999,
            max_pages=1,
        ),
        op_log=op,
    )
    assert out.kind == "killed"
    # After the 5-minute claim timeout Absurd hands the task to another worker.
    later = await drv.claim("sync_interactive", absurd_now=platform.clock.now().replace(year=2099))
    assert [t["task_id"] for t in later] == [task["task_id"]]
    from securefabric_domain.sync.handler import handle_slice

    result = await handle_slice(platform, run["id"], tenant.environment_id)
    assert result["outcome"] == "completed"
    run = (await runs(platform, tenant, job_id))["hosts"]
    assert run["state"] == "SUCCEEDED" and run["attempt"] == 1
    hosts = await rows(platform, tenant, cid, "data.resource")
    assert len([h for h in hosts if h["deleted_at"] is None]) == 12


async def test_an_admitted_run_whose_task_vanished_is_requeued(platform, tenant) -> None:
    from securefabric_domain.testing import reset_queues

    cid = await connection(platform, tenant)
    job_id = await demand(platform, tenant, cid, ["hosts"])
    drv = EngineDriver(platform)
    await drv.scheduler.admit()
    assert (await runs(platform, tenant, job_id))["hosts"]["state"] == "ADMITTED"
    async with platform.sys_pool.connection() as conn:  # the queue was emptied under it
        for prefix in ("c", "r", "t"):
            await conn.execute(f"delete from absurd.{prefix}_sync_interactive")  # noqa: S608 - fixed identifiers
    await drv.scheduler.expire()
    assert (await runs(platform, tenant, job_id))["hosts"]["state"] == "QUEUED"
    await drv.drain()
    assert (await runs(platform, tenant, job_id))["hosts"]["state"] == "SUCCEEDED"
    _ = reset_queues


async def test_schedules_follow_a_connector_release(platform, tenant) -> None:
    """A manifest change (e.g. a shorter reconcile cadence) reaches existing connections
    when the scheduler starts, and a shorter cadence takes effect now."""
    from datetime import timedelta

    from securefabric_db import fetch_all, system_tx
    from securefabric_domain.sync.jobs import reconcile_all_schedules
    from securefabric_domain.testing import make_connection

    cid = await make_connection(platform, tenant, credentials={"api_key": "sbx_sched_release"})
    manifest = platform.registry.manifest("SANDBOX")
    expected = {
        s.name: s.full_every
        for s in manifest.streams
        if s.full_every and s.sync_mode.value != "full"
    }
    assert expected, "the SANDBOX manifest declares a reconcile cadence"
    far = platform.clock.now() + timedelta(days=60)
    async with system_tx(platform.sys_pool) as conn:  # as if an older release had 4x the cadence
        await conn.execute(
            "update sync.stream_schedule set full_every_s = full_every_s * 4, next_full_at = %s "
            "where connection_id = %s and full_every_s is not null",
            (far, cid),
        )
    assert await reconcile_all_schedules(platform) >= 1
    async with system_tx(platform.sys_pool) as conn:
        rows = await fetch_all(
            conn,
            "select stream, full_every_s, next_full_at from sync.stream_schedule "
            "where connection_id = %s and full_every_s is not null",
            (cid,),
        )
    assert rows
    for r in rows:
        assert r["full_every_s"] == expected[r["stream"]]
        assert r["next_full_at"] <= platform.clock.now() + timedelta(seconds=r["full_every_s"])
