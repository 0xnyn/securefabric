"""Connect sessions and the hosted connect flow (CON-06..CON-09, part 3 section 8)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import Field

from securefabric_api.deps import ConnectPrincipalDep, IdempotencyDep, PlatformDep, PrincipalDep
from securefabric_api.schemas import RequestModel, ResponseModel, Timestamp
from securefabric_domain import connect as svc

router = APIRouter(prefix="/connect_sessions", tags=["connect"])
flow = APIRouter(prefix="/connect", tags=["connect"])


class SessionIn(RequestModel):
    organization_id: UUID
    integrations: list[str] | None = Field(
        default=None, description="Integration ids, keys or vendor names"
    )
    connection_id: UUID | None = Field(
        default=None, description="Re-authorise this connection (CON-09)"
    )
    option_presets: dict[str, Any] | None = None
    redirect_success: str | None = None
    redirect_error: str | None = None


class SessionCreated(ResponseModel):
    id: UUID
    token: str = Field(description="Bearer token for the connect UI. Shown once.")
    url: str = Field(description="Hosted connect page")
    expires_at: Timestamp
    organization_id: UUID
    connection_id: UUID | None = None


class SessionOut(ResponseModel):
    id: UUID
    organization_id: UUID
    allowed_integration_ids: list[UUID]
    connection_id: UUID | None = None
    redirect_success: str | None = None
    redirect_error: str | None = None
    expires_at: Timestamp
    used_at: Timestamp | None = None
    created_at: Timestamp


@router.post("", name="create_connect_session", status_code=201, dependencies=[IdempotencyDep])
async def create_session(
    body: SessionIn, principal: PrincipalDep, platform: PlatformDep
) -> SessionCreated:
    return SessionCreated(
        **await svc.create_session(
            platform,
            principal,
            organization_id=body.organization_id,
            integrations=body.integrations,
            connection_id=body.connection_id,
            option_presets=body.option_presets,
            redirect_success=body.redirect_success,
            redirect_error=body.redirect_error,
        )
    )


@router.get("", name="list_connect_sessions")
async def list_sessions(
    principal: PrincipalDep, platform: PlatformDep, organizationId: UUID | None = None
) -> list[SessionOut]:
    return [SessionOut(**s) for s in await svc.list_sessions(platform, principal, organizationId)]


class ConnectSessionView(ResponseModel):
    id: UUID
    organization: dict[str, Any] | None = None
    expires_at: Timestamp
    used_at: Timestamp | None = None
    reauthorize_connection_id: UUID | None = None
    option_presets: dict[str, Any] = Field(default_factory=dict)
    integrations: list[dict[str, Any]]
    branding: dict[str, Any]
    redirect_success: str | None = None
    redirect_error: str | None = None


@flow.get(
    "/session",
    name="get_connect_session",
    summary="What the connect UI renders (session token auth)",
)
async def get_session(principal: ConnectPrincipalDep, platform: PlatformDep) -> ConnectSessionView:
    return ConnectSessionView(**await svc.session_view(platform, principal))


class ConnectIn(RequestModel):
    integration: str
    credentials: dict[str, Any] | None = None
    options: dict[str, Any] | None = None
    mode: str = Field(
        default="install", description="install | authorize (the app is already installed)"
    )


class ConnectOut(ResponseModel):
    id: UUID
    state: str
    authorize_url: str | None = None


@flow.post("/connections", name="connect_create_connection", status_code=201)
async def connect_create(
    body: ConnectIn, principal: ConnectPrincipalDep, platform: PlatformDep
) -> ConnectOut:
    return ConnectOut(
        **await svc.connect_create(
            platform,
            principal,
            integration=body.integration,
            credentials=body.credentials,
            options=body.options,
            mode=body.mode,
        )
    )


class Verification(ResponseModel):
    reason: str = Field(description="create | rotate | test | reprobe | reauthorize | restore")
    status: str = Field(description="running | success | failed")
    message: str | None = Field(
        default=None, description="The vendor's rejection, or the verified tenant's name"
    )
    at: Timestamp


class ConnectStatus(ResponseModel):
    id: UUID
    state: str
    health_code: str
    pending_detail: str | None = None
    grants: list[dict[str, Any]] = Field(default_factory=list)
    missing_permissions: list[str] = Field(default_factory=list)
    last_verification: Verification | None = None


@flow.get("/connections/{connection_id}", name="connect_connection_status")
async def connect_status(
    connection_id: UUID, principal: ConnectPrincipalDep, platform: PlatformDep
) -> ConnectStatus:
    return ConnectStatus(**await svc.connect_status(platform, principal, connection_id))


@flow.get("/local/{connector}/{path:path}", name="connect_local_vendor", include_in_schema=False)
async def local_vendor(
    connector: str, path: str, request: Request, platform: PlatformDep
) -> RedirectResponse:
    """The authorize page of an in-process vendor (SANDBOX_OAUTH): the "vendor"
    approves at once and sends the browser back to our callback with a code."""
    target = await svc.local_vendor_page(platform, connector, path, dict(request.query_params))
    return RedirectResponse(target, status_code=302)


@flow.get("/callback/{connector}", name="connect_callback", include_in_schema=False)
async def callback(connector: str, request: Request, platform: PlatformDep) -> RedirectResponse:
    target, _ = await svc.handle_callback(platform, connector, dict(request.query_params))
    return RedirectResponse(target, status_code=302)
