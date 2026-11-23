"""Write-back actions (ACT-02, ACT-03; part 7 section 7)."""

import re
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Request
from pydantic import Field

from securefabric_api.deps import IdempotencyDep, PlatformDep, PrincipalDep
from securefabric_api.schemas import RequestModel, ResponseModel, Timestamp
from securefabric_domain import actions as svc

router = APIRouter(tags=["actions"])


class ActionIn(RequestModel):
    action: str = Field(description="set_state")
    state: str = Field(description="OPEN | IGNORED | CLOSED")
    reason: str | None = Field(
        default=None, description="false_positive | accepted_risk | test_code | revoked"
    )
    comment: str | None = Field(default=None, max_length=2000)


class ActionOut(ResponseModel):
    id: UUID
    connection_id: UUID
    finding_id: UUID
    name: str
    params: dict[str, Any]
    status: str
    vendor_response: dict[str, Any] | None = None
    message: str | None = None
    created_at: Timestamp
    finished_at: Timestamp | None = None


def _wait(prefer: str | None) -> float:
    m = re.search(r"wait=(\d+)", prefer or "")
    return min(float(m.group(1)), 30.0) if m else 0.0


@router.post(
    "/vulnerability_findings/{finding_id}/actions",
    name="create_action",
    status_code=202,
    dependencies=[IdempotencyDep],
)
async def create_action(
    finding_id: UUID,
    body: ActionIn,
    request: Request,
    principal: PrincipalDep,
    platform: PlatformDep,
    x_connection_id: Annotated[str | None, Header(alias="X-CONNECTION-ID")] = None,
    x_organization_id: Annotated[str | None, Header(alias="X-ORGANIZATION-ID")] = None,
    prefer: Annotated[str | None, Header()] = None,
) -> ActionOut:
    row = await svc.request_action(
        platform,
        principal,
        finding_id,
        body.model_dump(),
        connection_header=x_connection_id,
        organization_header=x_organization_id,
        idempotency_key=request.headers.get("idempotency-key"),
    )
    wait = _wait(prefer)
    if wait:
        row = await svc.get_action(platform, principal, row["id"], wait_s=wait)
    return ActionOut(**row)


@router.get("/actions/{action_id}", name="get_action")
async def get_action(
    action_id: UUID,
    principal: PrincipalDep,
    platform: PlatformDep,
    prefer: Annotated[str | None, Header()] = None,
) -> ActionOut:
    return ActionOut(**await svc.get_action(platform, principal, action_id, wait_s=_wait(prefer)))
