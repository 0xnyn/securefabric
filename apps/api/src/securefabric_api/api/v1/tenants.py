from typing import Annotated

from fastapi import APIRouter, Header, Request, status

from securefabric_api.api.v1.schemas import TaskAccepted
from securefabric_api.dependencies import AbsurdDep
from securefabric_tasks import PROVISION_TENANT, ProvisionTenantParams

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Provision a tenant (durable background workflow)",
)
async def provision_tenant(
    body: ProvisionTenantParams,
    absurd: AbsurdDep,
    request: Request,
    idempotency_key: Annotated[str | None, Header(max_length=255)] = None,
) -> TaskAccepted:
    """Enqueue the ``provision-tenant`` workflow and return immediately.

    Send an ``Idempotency-Key`` header to make retries of this request safe: the same
    key always maps to the same task. Defaults to the tenant id.
    """
    spawned = await PROVISION_TENANT.spawn(
        absurd,
        body,
        idempotency_key=idempotency_key or f"provision-tenant:{body.tenant_id}",
        headers={"request_id": request.headers.get("x-request-id", "")},
    )
    return TaskAccepted(
        task_id=spawned["task_id"],
        run_id=spawned["run_id"],
        attempt=spawned["attempt"],
        task_name=PROVISION_TENANT.name,
        queue=PROVISION_TENANT.queue,
        status_url=str(
            request.url_for("get_task", task_id=spawned["task_id"]).include_query_params(
                queue=PROVISION_TENANT.queue
            )
        ),
    )
