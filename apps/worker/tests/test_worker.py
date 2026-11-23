from collections.abc import Awaitable, Callable
from typing import Any, cast

import pytest
from absurd_sdk import AsyncAbsurd, AsyncTaskContext

from securefabric_db import DatabaseSettings, create_pool
from securefabric_domain import seed, service
from securefabric_domain.models import ConnectionCreate, CustomerInput
from securefabric_tasks import (
    SYNC_CONNECTION,
    AbsurdSettings,
    ProvisionTenantParams,
    SyncConnectionParams,
)
from securefabric_worker.config import WorkerSettings
from securefabric_worker.handlers.tenants import provision_tenant
from securefabric_worker.main import build_client, ensure_queue


class FakeContext:
    """Duck-typed AsyncTaskContext that records steps and sleeps."""

    task_id = "task-xyz"

    def __init__(self) -> None:
        self.steps: list[str] = []
        self.sleeps: list[tuple[str, float]] = []

    async def step(self, name: str, fn: Callable[[], Awaitable[Any]]) -> Any:
        self.steps.append(name)
        return await fn()

    async def sleep_for(self, name: str, duration: float) -> None:
        self.sleeps.append((name, duration))


def _params(**overrides: Any) -> ProvisionTenantParams:
    return ProvisionTenantParams.model_validate(
        {"tenant_id": "acme", "admin_email": "ops@acme.io"} | overrides
    )


async def test_provision_tenant_runs_steps_in_order() -> None:
    ctx = FakeContext()
    result = await provision_tenant(_params(plan="pro"), cast(AsyncTaskContext, ctx))
    assert ctx.steps == ["allocate-resources", "activate"]
    assert ctx.sleeps == []
    assert result.resources == ["db:acme", "bucket:acme", "replica:acme"]


async def test_provision_tenant_sleeps_durably_when_delayed() -> None:
    ctx = FakeContext()
    result = await provision_tenant(
        _params(activation_delay_seconds=5), cast(AsyncTaskContext, ctx)
    )
    assert ctx.sleeps == [("activation-delay", 5)]
    assert result.resources == ["db:acme", "bucket:acme"]


def test_worker_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKER_CONCURRENCY", "16")
    monkeypatch.setenv("WORKER_QUEUE_CLEANUP_TTL", "7 days")
    settings = WorkerSettings(_env_file=None)
    assert settings.concurrency == 16
    assert settings.queue_cleanup_ttl == "7 days"


@pytest.mark.integration
async def test_worker_processes_provision_task_end_to_end(database_url: str) -> None:
    """Uses the real handler registry against Postgres on the default queue."""
    settings = WorkerSettings(_env_file=None)
    db = DatabaseSettings(url=database_url, pool_min_size=0, pool_max_size=2)
    pool = create_pool(db)
    await pool.open()
    client: AsyncAbsurd = build_client(settings, db, AbsurdSettings(), pool)
    try:
        await ensure_queue(client, settings)
        spawned = await client.spawn(
            "provision-tenant", _params(tenant_id="e2e-tenant").model_dump(mode="json")
        )
        # Drain until our task completes (the shared queue may hold leftovers).
        for _ in range(20):
            await client.work_batch(worker_id="pytest", batch_size=10)
            snap = await client.fetch_task_result(spawned["task_id"])
            if snap is not None and snap.state == "completed":
                break
        assert snap is not None
        assert snap.state == "completed", snap.failure
        assert isinstance(snap.result, dict)
        assert snap.result["tenant_id"] == "e2e-tenant"
    finally:
        await client.close()
        await pool.close()


@pytest.mark.integration
async def test_sync_connection_task_finishes_the_job(database_url: str) -> None:
    """API-side start_sync + the real sync handler: the job ends SUCCESS, exactly once."""
    settings = WorkerSettings(_env_file=None)
    db = DatabaseSettings(url=database_url, pool_min_size=0, pool_max_size=2)
    pool = create_pool(db)
    await pool.open()
    client: AsyncAbsurd = build_client(settings, db, AbsurdSettings(), pool)
    try:
        await ensure_queue(client, settings)
        async with pool.connection() as conn:
            await seed(conn, reset=True)
            connection_id, job_id = await service.create_connection(
                conn,
                "dev",
                ConnectionCreate(
                    integration_id="okta",
                    sandbox=True,
                    customer=CustomerInput(email="a@b.co", end_user_id="org_1", org_name="B Co"),
                ),
            )
        spawned = await SYNC_CONNECTION.spawn(
            client,
            SyncConnectionParams(connection_id=connection_id, job_id=job_id, duration_seconds=0),
        )
        for _ in range(20):
            await client.work_batch(worker_id="pytest", batch_size=10)
            snap = await client.fetch_task_result(spawned["task_id"])
            if snap is not None and snap.state == "completed":
                break
        assert snap is not None
        assert snap.state == "completed", snap.failure
        assert SYNC_CONNECTION.parse_result(snap.result).status == "SUCCESS"
        async with pool.connection() as conn:
            row = await conn.execute("select status from fabric.sync_jobs where id = %s", (job_id,))
            assert await row.fetchone() == ("SUCCESS",)
    finally:
        await client.close()
        await pool.close()
