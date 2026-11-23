"""Organizations: the customer's end customers (TEN-03, TEN-04)."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from securefabric_api.deps import (
    IdempotencyDep,
    PlatformDep,
    PrincipalDep,
    allow_params,
    csv,
    uuids,
)
from securefabric_api.routes.common import Page, page
from securefabric_api.schemas import RequestModel, ResponseModel, Timestamp
from securefabric_domain import tenancy

router = APIRouter(prefix="/organizations", tags=["organizations"])


class OrganizationOut(ResponseModel):
    id: UUID
    identifier: str
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    connection_count: int = 0
    created_at: Timestamp
    updated_at: Timestamp


class OrganizationIn(RequestModel):
    identifier: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    metadata: dict[str, Any] | None = None


class OrganizationPatch(RequestModel):
    identifier: str | None = Field(default=None, min_length=1, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    metadata: dict[str, Any] | None = None


@router.post("", name="create_organization", status_code=201, dependencies=[IdempotencyDep])
async def create_organization(
    body: OrganizationIn, principal: PrincipalDep, platform: PlatformDep
) -> OrganizationOut:
    return OrganizationOut(
        **await tenancy.create_organization(
            platform, principal, identifier=body.identifier, name=body.name, metadata=body.metadata
        )
    )


@router.get(
    "",
    name="list_organizations",
    dependencies=[Depends(allow_params("name", "identifier", "id", "ids", "search"))],
)
async def list_organizations(
    principal: PrincipalDep,
    platform: PlatformDep,
    name: str | None = None,
    identifier: str | None = None,
    id: Annotated[str | None, Query()] = None,
    ids: str | None = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> Page[OrganizationOut]:
    p = await tenancy.list_organizations(
        platform,
        principal,
        name=name,
        identifier=identifier,
        ids=uuids(csv(ids) or csv(id), "ids"),
        search=search,
        cursor=cursor,
        limit=limit,
    )
    return Page[OrganizationOut](**page(p))


@router.get("/{organization_id}", name="get_organization")
async def get_organization(
    organization_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> OrganizationOut:
    return OrganizationOut(**await tenancy.read_organization(platform, principal, organization_id))


@router.patch("/{organization_id}", name="update_organization")
async def update_organization(
    organization_id: UUID, body: OrganizationPatch, principal: PrincipalDep, platform: PlatformDep
) -> OrganizationOut:
    return OrganizationOut(
        **await tenancy.update_organization(
            platform,
            principal,
            organization_id,
            name=body.name,
            identifier=body.identifier,
            metadata=body.metadata,
        )
    )


@router.delete("/{organization_id}", name="delete_organization", status_code=204)
async def delete_organization(
    organization_id: UUID, principal: PrincipalDep, platform: PlatformDep
) -> None:
    await tenancy.delete_organization(platform, principal, organization_id)
