"""Operation log (OBS-01/02), usage (BILL-03) and alerts (operators)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import Field

from securefabric_api.deps import PlatformDep, PrincipalDep, allow_params, csv
from securefabric_api.routes.common import Page, page
from securefabric_api.schemas import ResponseModel, Timestamp
from securefabric_domain import ops

router = APIRouter(tags=["observability"])


class OperationOut(ResponseModel):
    id: UUID
    kind: str
    action: str
    status: str
    vendor: str | None = None
    connection_id: UUID | None = None
    organization_id: UUID | None = None
    job_id: UUID | None = None
    stream_run_id: UUID | None = None
    request_id: str | None = None
    started_at: Timestamp
    duration_ms: int | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    line_count: int = 0


class OperationLine(ResponseModel):
    at: Timestamp
    level: str
    kind: str
    message: str
    http: dict[str, Any] | None = None


class OperationDetail(OperationOut):
    lines: list[OperationLine] = Field(default_factory=list)


@router.get(
    "/operations",
    name="list_operations",
    dependencies=[Depends(allow_params("kind", "status", "connectionId", "jobId", "since"))],
)
async def list_operations(
    principal: PrincipalDep,
    platform: PlatformDep,
    kind: str | None = None,
    status: str | None = None,
    connectionId: UUID | None = None,
    jobId: UUID | None = None,
    since: datetime | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> Page[OperationOut]:
    p = await ops.list_operations(
        platform,
        principal,
        kind=csv(kind),
        status=csv(status),
        connection_id=connectionId,
        job_id=jobId,
        since=since,
        cursor=cursor,
        limit=limit,
    )
    return Page[OperationOut](**page(p))


@router.get("/operations/{operation_id}", name="get_operation")
async def get_operation(
    operation_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> OperationDetail:
    return OperationDetail(**await ops.get_operation(platform, principal, operation_id))


class Usage(ResponseModel):
    live: dict[str, Any]
    daily: list[dict[str, Any]]
    api_calls_by_hour: list[dict[str, Any]]


@router.get("/usage", name="get_usage", summary="Read-only usage counters (BILL-03)")
async def get_usage(principal: PrincipalDep, platform: PlatformDep, days: int = 30) -> Usage:
    return Usage(**await ops.usage(platform, principal, days=min(max(days, 1), 400)))
