import dataclasses
import uuid
from typing import Any, cast

import pytest
from absurd_sdk import AsyncAbsurd, AsyncTaskContext
from pydantic import ValidationError

from securefabric_tasks import PROVISION_TENANT, ProvisionTenantParams, ProvisionTenantResult


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, dict[str, Any]]] = []

    async def spawn(self, task_name: str, params: Any, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((task_name, params, kwargs))
        # Real SDK returns uuid.UUID objects despite annotating str.
        return {"task_id": uuid.UUID(int=1), "run_id": uuid.UUID(int=2), "attempt": 1}


def _params(**overrides: Any) -> ProvisionTenantParams:
    data: dict[str, Any] = {"tenant_id": "acme", "admin_email": "ops@acme.io"} | overrides
    return ProvisionTenantParams.model_validate(data)


@pytest.mark.parametrize("tenant_id", ["A", "ab", "-acme", "acme-", "ac me", "x" * 41])
def test_params_reject_bad_tenant_ids(tenant_id: str) -> None:
    with pytest.raises(ValidationError):
        _params(tenant_id=tenant_id)


def test_params_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        _params(surprise=True)


async def test_spawn_sends_json_params_and_spec_defaults() -> None:
    client = RecordingClient()
    result = await PROVISION_TENANT.spawn(
        cast(AsyncAbsurd, client), _params(plan="pro"), idempotency_key="k1"
    )
    assert result == {
        "task_id": str(uuid.UUID(int=1)),
        "run_id": str(uuid.UUID(int=2)),
        "attempt": 1,
    }
    name, params, kwargs = client.calls[0]
    assert name == "provision-tenant"
    assert params == {
        "tenant_id": "acme",
        "plan": "pro",
        "admin_email": "ops@acme.io",
        "activation_delay_seconds": 0,
    }
    assert kwargs["queue"] == PROVISION_TENANT.queue
    assert kwargs["max_attempts"] == PROVISION_TENANT.max_attempts
    assert kwargs["idempotency_key"] == "k1"


# ---------------------------------------------------------------------------
# Integration: real Absurd round-trip through Postgres
# ---------------------------------------------------------------------------


async def _echo_handler(
    params: ProvisionTenantParams, ctx: AsyncTaskContext
) -> ProvisionTenantResult:
    async def resources() -> list[str]:
        return [f"db:{params.tenant_id}"]

    allocated = await ctx.step("alloc", resources)
    if params.activation_delay_seconds:
        await ctx.sleep_for("wait", params.activation_delay_seconds)
    return ProvisionTenantResult(
        tenant_id=params.tenant_id,
        plan=params.plan,
        resources=allocated,
        activated_at="2026-01-01T00:00:00Z",
    )


@pytest.mark.integration
async def test_spawn_work_and_fetch_result(database_url: str, unique_queue: str) -> None:
    spec = dataclasses.replace(PROVISION_TENANT, queue=unique_queue)
    client = AsyncAbsurd(database_url, queue_name=unique_queue)
    try:
        await client.create_queue(unique_queue)
        spec.register(client, _echo_handler)

        spawned = await spec.spawn(client, _params(), idempotency_key="same")
        again = await spec.spawn(client, _params(), idempotency_key="same")
        assert again["task_id"] == spawned["task_id"], "idempotency key must dedupe"

        pending = await client.fetch_task_result(spawned["task_id"])
        assert pending is not None
        assert pending.state == "pending"

        await client.work_batch(worker_id="pytest", batch_size=5)

        done = await client.fetch_task_result(spawned["task_id"])
        assert done is not None
        assert done.state == "completed", done.failure
        result = spec.parse_result(done.result)
        assert result.resources == ["db:acme"]
    finally:
        await client.close()


@pytest.mark.integration
async def test_durable_sleep_suspends_task(database_url: str, unique_queue: str) -> None:
    spec = dataclasses.replace(PROVISION_TENANT, queue=unique_queue)
    client = AsyncAbsurd(database_url, queue_name=unique_queue)
    try:
        await client.create_queue(unique_queue)
        spec.register(client, _echo_handler)
        spawned = await spec.spawn(client, _params(activation_delay_seconds=3600))

        await client.work_batch(worker_id="pytest")

        snapshot = await client.fetch_task_result(spawned["task_id"])
        assert snapshot is not None
        assert snapshot.state == "sleeping"
    finally:
        await client.close()
