"""Handlers for tenant lifecycle workflows.

Absurd replays a task from the top on every resume/retry, returning cached values
for steps that already completed. So: put side effects *inside* ``ctx.step(...)``
and keep code outside steps deterministic.
"""

from datetime import UTC, datetime

from absurd_sdk import AsyncAbsurd, AsyncTaskContext

from securefabric_core import get_logger
from securefabric_db import AsyncPool
from securefabric_tasks import PROVISION_TENANT, ProvisionTenantParams, ProvisionTenantResult

log = get_logger(__name__)


async def provision_tenant(
    params: ProvisionTenantParams, ctx: AsyncTaskContext
) -> ProvisionTenantResult:
    bound = log.bind(task_id=str(ctx.task_id), tenant_id=params.tenant_id)

    async def allocate_resources() -> list[str]:
        bound.info("allocating_resources", plan=params.plan)
        # Replace with real calls (create DB schema, bucket, keys, ...). Must be idempotent.
        base = [f"db:{params.tenant_id}", f"bucket:{params.tenant_id}"]
        return [*base, f"replica:{params.tenant_id}"] if params.plan != "free" else base

    resources = await ctx.step("allocate-resources", allocate_resources)

    if params.activation_delay_seconds:
        # Durable sleep: the worker is released; the task resumes after the delay,
        # even across deploys/restarts, and skips the completed step above.
        await ctx.sleep_for("activation-delay", params.activation_delay_seconds)

    async def activate() -> str:
        bound.info("activating_tenant", admin_email=params.admin_email)
        return datetime.now(UTC).isoformat()

    activated_at = await ctx.step("activate", activate)

    bound.info("tenant_provisioned", resources=len(resources))
    return ProvisionTenantResult(
        tenant_id=params.tenant_id,
        plan=params.plan,
        resources=resources,
        activated_at=datetime.fromisoformat(activated_at),
    )


def register(client: AsyncAbsurd, pool: AsyncPool) -> None:
    PROVISION_TENANT.register(client, provision_tenant)
