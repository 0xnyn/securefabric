"""Data endpoints: resources and vulnerability findings (Leen V2 compatible, API-01..API-13)."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from pydantic import ConfigDict, Field

from securefabric_api.deps import PlatformDep, PrincipalDep, allow_params, csv, parse_bool, uuids
from securefabric_api.routes.common import Page, page
from securefabric_api.schemas import ResponseModel
from securefabric_core import ValidationFailedError
from securefabric_domain import data_api as svc

router = APIRouter(tags=["data"])

ConnHeader = Annotated[str | None, Header(alias="X-CONNECTION-ID")]
OrgHeader = Annotated[str | None, Header(alias="X-ORGANIZATION-ID")]


class _Open(ResponseModel):
    model_config = ConfigDict(extra="allow", json_schema_serialization_defaults_required=True)


class VendorAttributes(_Open):
    id: str
    url: str | None = None
    severity: str | None = None
    state: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    vulnerability_identifiers: list[dict[str, Any]] = Field(default_factory=list)
    data: dict[str, Any] | None = None


class ResourceVendorAttributes(_Open):
    id: str
    data: dict[str, Any] | None = None


class Meta(_Open):
    derived: list[str] = Field(default_factory=list)
    stream: str
    connector_version: str | None = None
    natural_key: str


class ResourceOut(_Open):
    id: str
    name: str
    type: str
    state: str
    vendor: str
    url: str | None = None
    groups: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[dict[str, Any]] = Field(default_factory=list)
    first_seen: str | None = None
    last_seen: str | None = None
    cloud_metadata: dict[str, Any] | None = None
    data: dict[str, Any] | None = None
    vendor_attributes: ResourceVendorAttributes
    connection_id: str
    organization_id: str
    is_stub: bool = False
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    meta: Meta = Field(alias="_meta", serialization_alias="_meta")


class ResourceRef(_Open):
    id: str
    name: str
    type: str
    state: str
    vendor: str
    url: str | None = None
    role: str | None = None
    vendor_attributes: ResourceVendorAttributes


class FindingOut(_Open):
    id: str
    title: str | None = None
    description: str | None = None
    severity: str
    state: str
    type: str
    has_fix: bool | None = None
    exploitable: bool | None = None
    reachability: str | None = None
    remediation: str | None = None
    analytic: dict[str, Any] | None = None
    analytic_output: str | None = None
    product: dict[str, Any] | None = None
    ticket: dict[str, Any] | None = None
    resource_related: list[dict[str, Any]] = Field(default_factory=list)
    resources: list[dict[str, Any]] = Field(default_factory=list)
    vulnerabilities: list[dict[str, Any]] = Field(default_factory=list)
    vendor_attributes: VendorAttributes
    first_seen: str | None = None
    last_seen: str | None = None
    state_updated_at: str | None = None
    connection_id: str
    organization_id: str
    cve_ids: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None
    enrichment: dict[str, Any] | None = None
    meta: Meta = Field(alias="_meta", serialization_alias="_meta")


FINDING_PARAMS = (
    "severity",
    "state",
    "type",
    "has_fix",
    "reachability",
    "exploitable",
    "firstSeenSince",
    "lastSeenSince",
    "stateUpdatedSince",
    "updatedSince",
    "resourceId",
    "ids",
    "cveId",
    "changeType",
    "connectionId",
    "include",
    "sort",
)


@router.get(
    "/vulnerability_findings",
    name="list_vulnerability_findings",
    response_model_by_alias=True,
    dependencies=[Depends(allow_params(*FINDING_PARAMS))],
)
async def list_findings(
    principal: PrincipalDep,
    platform: PlatformDep,
    response: Response,
    x_connection_id: ConnHeader = None,
    x_organization_id: OrgHeader = None,
    severity: str | None = None,
    state: str | None = None,
    type: str | None = None,
    has_fix: str | None = None,
    reachability: str | None = None,
    exploitable: str | None = None,
    firstSeenSince: datetime | None = None,
    lastSeenSince: datetime | None = None,
    stateUpdatedSince: datetime | None = None,
    updatedSince: datetime | None = None,
    resourceId: str | None = None,
    ids: str | None = None,
    cveId: str | None = None,
    changeType: str | None = None,
    connectionId: str | None = None,
    include: str | None = None,
    sort: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> Page[FindingOut]:
    if include not in (None, "resources"):
        raise ValidationFailedError(
            "include accepts only 'resources'.",
            code="invalid_filter",
            errors=[{"field": "include", "message": "only 'resources'"}],
        )
    q = svc.FindingQuery(
        severity=svc.enum_filter(csv(severity), "severity", "severity"),
        state=svc.enum_filter(csv(state), "state", "state"),
        type=svc.enum_filter(csv(type), "type", "type"),
        has_fix=parse_bool("has_fix", has_fix),
        exploitable=parse_bool("exploitable", exploitable),
        reachability=svc.enum_filter(csv(reachability), "reachability", "reachability"),
        first_seen_since=firstSeenSince,
        last_seen_since=lastSeenSince,
        state_updated_since=stateUpdatedSince,
        updated_since=updatedSince,
        resource_ids=uuids(csv(resourceId), "resourceId"),
        ids=uuids(csv(ids), "ids"),
        cve_ids=csv(cveId),
        change_type=csv(changeType),
        connection_ids=uuids(csv(connectionId), "connectionId"),
        include_resources=include == "resources",
        sort=sort,
    )
    p, unsupported = await svc.list_findings(
        platform,
        principal,
        q,
        connection_header=x_connection_id,
        organization_header=x_organization_id,
        cursor=cursor,
        limit=limit,
    )
    if unsupported:
        response.headers["X-Unsupported-Filters"] = ",".join(unsupported)
    return Page[FindingOut](**page(p))


class Summary(ResponseModel):
    total: int
    by_severity: dict[str, int]
    by_state: dict[str, int]
    by_type: dict[str, int]
    open_by_severity: dict[str, int]


@router.get(
    "/vulnerability_findings/summary",
    name="findings_summary",
    summary="Counts by severity, state and type",
)
async def summary(
    principal: PrincipalDep,
    platform: PlatformDep,
    x_connection_id: ConnHeader = None,
    x_organization_id: OrgHeader = None,
) -> Summary:
    return Summary(
        **await svc.findings_summary(
            platform,
            principal,
            connection_header=x_connection_id,
            organization_header=x_organization_id,
        )
    )


@router.get(
    "/vulnerability_findings/{finding_id}",
    name="get_vulnerability_finding",
    response_model_by_alias=True,
)
async def get_finding(
    finding_id: str,
    principal: PrincipalDep,
    platform: PlatformDep,
    x_connection_id: ConnHeader = None,
    x_organization_id: OrgHeader = None,
    include: str | None = "resources",
) -> FindingOut:
    [fid] = uuids([finding_id], "finding_id") or []
    return FindingOut(
        **await svc.get_finding(
            platform,
            principal,
            fid,
            connection_header=x_connection_id,
            organization_header=x_organization_id,
        )
    )


class HistoryOut(ResponseModel):
    from_state: str | None = None
    to_state: str
    at: str
    source: str
    stream_run_id: UUID | None = None


@router.get("/vulnerability_findings/{finding_id}/history", name="get_finding_history")
async def history(
    finding_id: str,
    principal: PrincipalDep,
    platform: PlatformDep,
    x_connection_id: ConnHeader = None,
    x_organization_id: OrgHeader = None,
) -> list[HistoryOut]:
    [fid] = uuids([finding_id], "finding_id") or []
    return [
        HistoryOut(**h)
        for h in await svc.finding_history(
            platform,
            principal,
            fid,
            connection_header=x_connection_id,
            organization_header=x_organization_id,
        )
    ]


@router.get(
    "/resources",
    name="list_resources",
    response_model_by_alias=True,
    dependencies=[
        Depends(
            allow_params(
                "name",
                "vendor",
                "state",
                "type",
                "updatedSince",
                "ids",
                "changeType",
                "connectionId",
                "sort",
            )
        )
    ],
)
async def list_resources(
    principal: PrincipalDep,
    platform: PlatformDep,
    x_connection_id: ConnHeader = None,
    x_organization_id: OrgHeader = None,
    name: str | None = None,
    vendor: str | None = None,
    state: str | None = None,
    type: str | None = None,
    updatedSince: datetime | None = None,
    ids: str | None = None,
    changeType: str | None = None,
    connectionId: str | None = None,
    sort: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> Page[ResourceOut]:
    q = svc.ResourceQuery(
        name=csv(name),
        vendor=csv(vendor),
        state=svc.enum_filter(csv(state), "resource_state", "state"),
        type=svc.enum_filter(csv(type), "resource_type", "type"),
        updated_since=updatedSince,
        ids=uuids(csv(ids), "ids"),
        change_type=csv(changeType),
        connection_ids=uuids(csv(connectionId), "connectionId"),
        sort=sort,
    )
    p = await svc.list_resources(
        platform,
        principal,
        q,
        connection_header=x_connection_id,
        organization_header=x_organization_id,
        cursor=cursor,
        limit=limit,
    )
    return Page[ResourceOut](**page(p))


@router.get("/resources/{resource_id}", name="get_resource", response_model_by_alias=True)
async def get_resource(
    resource_id: str,
    principal: PrincipalDep,
    platform: PlatformDep,
    x_connection_id: ConnHeader = None,
    x_organization_id: OrgHeader = None,
) -> ResourceOut:
    [rid] = uuids([resource_id], "resource_id") or []
    return ResourceOut(
        **await svc.get_resource(
            platform,
            principal,
            rid,
            connection_header=x_connection_id,
            organization_header=x_organization_id,
        )
    )


@router.get(
    "/enrichments/cves/{cve_id}",
    name="get_cve",
    summary="CVE mirror lookup: NVD, KEV, EPSS, aliases (ENR-04)",
)
async def get_cve(cve_id: str, principal: PrincipalDep, platform: PlatformDep) -> dict[str, Any]:
    return await svc.get_cve(platform, principal, cve_id)
