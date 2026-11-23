"""Passthrough (RAW-01) and the operator admin console (OPS-01/05/08, RAW-02)."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import Field

from securefabric_api.deps import PlatformDep, PrincipalDep
from securefabric_api.schemas import RequestModel, ResponseModel
from securefabric_domain import operator, passthrough

router = APIRouter(tags=["admin"])
# Required on every operator action inside a customer environment; audited with it.
Reason = Annotated[
    str,
    Header(
        alias="X-Support-Reason",
        min_length=5,
        max_length=500,
        description="Why an operator is acting in this customer's environment (audited)",
    ),
]
RepairAction = Literal[
    "trigger", "pause", "resume", "reset", "renormalize", "purge_now", "rebuild_counts", "reprobe"
]


class AlertOut(ResponseModel):
    id: UUID
    name: str
    severity: Literal["page", "ticket", "info"]
    subject: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    runbook: str | None = Field(default=None, description="Path under docs/runbooks")
    raised_at: datetime
    resolved_at: datetime | None = None


class RepairFailure(ResponseModel):
    name: str | None = None
    message: str | None = None


class RepairTask(ResponseModel):
    task_id: str
    state: Literal["pending", "running", "sleeping", "completed", "failed", "cancelled"]
    result: dict[str, Any] | None = None
    failure: RepairFailure | None = None


class PassthroughIn(RequestModel):
    method: str = "GET"
    path: str = Field(
        description="Vendor API path; must match the connector's passthrough allowlist"
    )
    query: dict[str, str] | None = None


class PassthroughOut(ResponseModel):
    status: int | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = None
    truncated: bool = False
    error: str | None = None


@router.post(
    "/connections/{connection_id}/passthrough",
    name="passthrough",
    tags=["connections"],
    summary="Read-only vendor request, allowlisted per connector (RAW-01)",
)
async def do_passthrough(
    connection_id: UUID, body: PassthroughIn, principal: PrincipalDep, platform: PlatformDep
) -> PassthroughOut:
    return PassthroughOut(
        **await passthrough.request(
            platform, principal, connection_id, method=body.method, path=body.path, query=body.query
        )
    )


@router.get(
    "/admin/search", name="admin_search", summary="Operators: find connections across accounts"
)
async def search(q: str, principal: PrincipalDep, platform: PlatformDep) -> list[dict[str, Any]]:
    return await operator.search(platform, principal, q)


@router.get(
    "/admin/scheduler",
    name="admin_scheduler",
    summary="Operators: queued, admitted, parked and retrying runs",
)
async def scheduler(principal: PrincipalDep, platform: PlatformDep) -> list[dict[str, Any]]:
    return await operator.scheduler_view(platform, principal)


@router.get(
    "/admin/alerts", name="admin_alerts", summary="Operators: open alerts (with their runbooks)"
)
async def alerts(
    principal: PrincipalDep, platform: PlatformDep, include_resolved: bool = False
) -> list[AlertOut]:
    from securefabric_domain.ops import list_alerts

    rows = await list_alerts(platform, principal, include_resolved=include_resolved)
    return [AlertOut(**r) for r in rows]


class ResolveIn(RequestModel):
    note: str = Field(min_length=1, max_length=500, description="What was done (shown in history)")


@router.post(
    "/admin/alerts/{alert_id}/resolve",
    name="admin_resolve_alert",
    summary="Operators: close an alert after following its runbook",
)
async def resolve_alert(
    alert_id: UUID, body: ResolveIn, principal: PrincipalDep, platform: PlatformDep
) -> AlertOut:
    from securefabric_domain.ops import resolve_alert as resolve

    return AlertOut(**await resolve(platform, principal, alert_id, body.note))


class RepairIn(RequestModel):
    params: dict[str, Any] = Field(default_factory=dict)


@router.post(
    "/admin/environments/{environment_id}/connections/{connection_id}/{action}",
    name="admin_repair",
    summary="Operators: trigger, pause, resume, reset, renormalize, purge_now, rebuild_counts, reprobe",
)
async def repair(
    environment_id: UUID,
    connection_id: UUID,
    action: RepairAction,
    body: RepairIn,
    principal: PrincipalDep,
    platform: PlatformDep,
    x_support_reason: Reason,
) -> dict[str, Any]:
    return await operator.repair(
        platform, principal, environment_id, connection_id, action, x_support_reason, body.params
    )


@router.get(
    "/admin/repairs/{task_id}",
    name="admin_repair_status",
    summary="Operators: the state and result of a queued repair (renormalize, purge_now, reprobe)",
)
async def repair_status(
    task_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> RepairTask:
    return RepairTask(**await operator.repair_status(platform, principal, task_id))


@router.get(
    "/admin/environments/{environment_id}/raw_pages",
    name="admin_raw_pages",
    summary="Operators: archived raw vendor pages of a connection or run (audited)",
)
async def raw_pages(
    environment_id: UUID,
    principal: PrincipalDep,
    platform: PlatformDep,
    x_support_reason: Reason,
    connectionId: UUID | None = None,
    runId: UUID | None = None,
) -> list[dict[str, Any]]:
    return await operator.raw_pages(
        platform,
        principal,
        environment_id,
        x_support_reason,
        connection_id=connectionId,
        run_id=runId,
    )


@router.get(
    "/admin/environments/{environment_id}/raw_pages/{raw_page_id}",
    name="admin_raw_page",
    summary="Operators: one archived raw page, opened in the control worker (audited)",
)
async def raw_page(
    environment_id: UUID,
    raw_page_id: UUID,
    principal: PrincipalDep,
    platform: PlatformDep,
    x_support_reason: Reason,
) -> dict[str, Any]:
    return await operator.view_raw_page(
        platform, principal, environment_id, raw_page_id, x_support_reason
    )
