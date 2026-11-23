"""Catalogue, integrations and vendor apps (CAT-01, CAT-02, PD-3, PD-10)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import Field

from securefabric_api.deps import IdempotencyDep, PlatformDep, PrincipalDep
from securefabric_api.schemas import RequestModel, ResponseModel, Timestamp
from securefabric_domain import catalog

public = APIRouter(prefix="/connectors", tags=["connectors"])
router = APIRouter(tags=["integrations"])


class ConnectorOut(ResponseModel):
    id: str
    version: str
    name: str
    description: str
    categories: list[str]
    status: str
    logo_url: str | None = None
    docs_url: str | None = None
    auth: dict[str, Any]
    credentials_schema: dict[str, Any]
    connection_config_schema: dict[str, Any]
    options_schema: dict[str, Any]
    regions: list[dict[str, Any]]
    permissions: list[dict[str, Any]]
    streams: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    data_types: list[str]
    capabilities: dict[str, Any] = Field(default_factory=dict)


@public.get("", name="list_connectors", summary="The public connector catalogue (no auth)")
async def list_connectors(platform: PlatformDep) -> list[ConnectorOut]:
    return [ConnectorOut(**c) for c in catalog.list_connectors(platform)]


@public.get("/{connector_id}", name="get_connector")
async def get_connector(connector_id: str, platform: PlatformDep) -> ConnectorOut:
    return ConnectorOut(**catalog.get_connector(platform, connector_id))


class IntegrationOut(ResponseModel):
    id: UUID
    key: str
    connector_id: str
    connector_version: str
    deprecated: bool
    display_name: str
    vendor_app_id: UUID | None = None
    enabled_streams: list[str]
    stream_intervals: dict[str, int]
    option_defaults: dict[str, Any]
    options_schema: dict[str, Any]
    write_back_enabled: bool
    capabilities: dict[str, Any] = Field(default_factory=dict)
    created_at: Timestamp


class IntegrationIn(RequestModel):
    connector_id: str
    key: str | None = Field(default=None, pattern=r"^[a-z0-9](?:[a-z0-9_-]*[a-z0-9])?$")
    display_name: str | None = None
    vendor_app_id: UUID | None = None
    enabled_streams: list[str] | None = None
    stream_intervals: dict[str, int] | None = None
    option_defaults: dict[str, Any] | None = None
    write_back_enabled: bool = False


class IntegrationPatch(RequestModel):
    display_name: str | None = None
    vendor_app_id: UUID | None = None
    enabled_streams: list[str] | None = None
    stream_intervals: dict[str, int] | None = None
    option_defaults: dict[str, Any] | None = None
    write_back_enabled: bool | None = None


@router.get("/integrations", name="list_integrations")
async def list_integrations(principal: PrincipalDep, platform: PlatformDep) -> list[IntegrationOut]:
    return [IntegrationOut(**i) for i in await catalog.list_integrations(platform, principal)]


@router.post(
    "/integrations", name="create_integration", status_code=201, dependencies=[IdempotencyDep]
)
async def create_integration(
    body: IntegrationIn, principal: PrincipalDep, platform: PlatformDep
) -> IntegrationOut:
    return IntegrationOut(
        **await catalog.create_integration(
            platform,
            principal,
            connector_id=body.connector_id,
            key=body.key,
            display_name=body.display_name,
            vendor_app_id=body.vendor_app_id,
            enabled_streams=body.enabled_streams,
            stream_intervals=body.stream_intervals,
            option_defaults_=body.option_defaults,
            write_back_enabled=body.write_back_enabled,
        )
    )


@router.get("/integrations/{integration_id}", name="get_integration")
async def get_integration(
    integration_id: str, principal: PrincipalDep, platform: PlatformDep
) -> IntegrationOut:
    return IntegrationOut(**await catalog.get_integration(platform, principal, integration_id))


@router.patch("/integrations/{integration_id}", name="update_integration")
async def update_integration(
    integration_id: str, body: IntegrationPatch, principal: PrincipalDep, platform: PlatformDep
) -> IntegrationOut:
    return IntegrationOut(
        **await catalog.update_integration(
            platform, principal, integration_id, body.model_dump(exclude_unset=True)
        )
    )


@router.delete("/integrations/{integration_id}", name="delete_integration", status_code=204)
async def delete_integration(
    integration_id: str, principal: PrincipalDep, platform: PlatformDep
) -> None:
    await catalog.delete_integration(platform, principal, integration_id)


class VendorAppOut(ResponseModel):
    id: UUID
    connector_id: str
    name: str
    base_url: str
    config: dict[str, Any]
    owner: str
    is_default: bool
    secrets_set: bool
    webhook_secret_set: bool
    created_at: Timestamp


class VendorAppIn(RequestModel):
    connector_id: str
    name: str
    base_url: str = Field(description="https://github.com, https://<sub>.ghe.com or a GHES host")
    config: dict[str, Any] = Field(
        description="Non-secret: app_id, slug, client_id, api_base_url, permission_tier"
    )
    secrets: dict[str, Any] = Field(description="Write-only: private_key, client_secret")
    webhook_secret: str | None = None


class VendorAppPatch(RequestModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    secrets: dict[str, Any] | None = None
    webhook_secret: str | None = None


@router.get("/vendor_apps", name="list_vendor_apps")
async def list_vendor_apps(principal: PrincipalDep, platform: PlatformDep) -> list[VendorAppOut]:
    return [VendorAppOut(**a) for a in await catalog.list_vendor_apps(platform, principal)]


@router.post(
    "/vendor_apps", name="create_vendor_app", status_code=201, dependencies=[IdempotencyDep]
)
async def create_vendor_app(
    body: VendorAppIn, principal: PrincipalDep, platform: PlatformDep
) -> VendorAppOut:
    return VendorAppOut(
        **await catalog.create_vendor_app(
            platform,
            principal,
            connector_id=body.connector_id,
            name=body.name,
            base_url=body.base_url,
            config=body.config,
            secrets=body.secrets,
            webhook_secret=body.webhook_secret,
        )
    )


@router.get("/vendor_apps/{vendor_app_id}", name="get_vendor_app")
async def get_vendor_app(
    vendor_app_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> VendorAppOut:
    return VendorAppOut(**await catalog.get_vendor_app(platform, principal, vendor_app_id))


@router.patch("/vendor_apps/{vendor_app_id}", name="update_vendor_app")
async def update_vendor_app(
    vendor_app_id: UUID, body: VendorAppPatch, principal: PrincipalDep, platform: PlatformDep
) -> VendorAppOut:
    return VendorAppOut(
        **await catalog.update_vendor_app(
            platform,
            principal,
            vendor_app_id,
            name=body.name,
            config=body.config,
            secrets=body.secrets,
            webhook_secret=body.webhook_secret,
        )
    )


@router.delete("/vendor_apps/{vendor_app_id}", name="delete_vendor_app", status_code=204)
async def delete_vendor_app(
    vendor_app_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> None:
    await catalog.delete_vendor_app(platform, principal, vendor_app_id)
