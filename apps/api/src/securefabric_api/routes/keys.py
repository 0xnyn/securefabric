"""API keys (TEN-06, TEN-07, TEN-08): create with scopes, shown once, revoke."""

from uuid import UUID

from fastapi import APIRouter
from pydantic import Field

from securefabric_api.deps import IdempotencyDep, PlatformDep, PrincipalDep
from securefabric_api.schemas import RequestModel, ResponseModel, Timestamp
from securefabric_domain import tenancy

router = APIRouter(prefix="/api_keys", tags=["api_keys"])


class ApiKeyOut(ResponseModel):
    id: UUID
    name: str
    prefix: str
    scopes: list[str]
    created_at: Timestamp
    last_used_at: Timestamp | None = None
    expires_at: Timestamp | None = None
    revoked_at: Timestamp | None = None
    created_by: UUID | None = None


class ApiKeyCreated(ApiKeyOut):
    key: str = Field(description="The full key. Shown once; store it now.")


class ApiKeyIn(RequestModel):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str] | None = Field(
        default=None, description=f"Defaults to all: {', '.join(tenancy.SCOPES)}"
    )
    expires_at: Timestamp | None = None


@router.get("", name="list_api_keys")
async def list_api_keys(principal: PrincipalDep, platform: PlatformDep) -> list[ApiKeyOut]:
    return [ApiKeyOut(**k) for k in await tenancy.list_api_keys(platform, principal)]


@router.post("", name="create_api_key", status_code=201, dependencies=[IdempotencyDep])
async def create_api_key(
    body: ApiKeyIn, principal: PrincipalDep, platform: PlatformDep
) -> ApiKeyCreated:
    row, key = await tenancy.create_api_key(
        platform, principal, name=body.name, scopes=body.scopes, expires_at=body.expires_at
    )
    return ApiKeyCreated(**row, key=key)


@router.delete("/{key_id}", name="revoke_api_key")
async def revoke_api_key(key_id: UUID, principal: PrincipalDep, platform: PlatformDep) -> ApiKeyOut:
    return ApiKeyOut(**await tenancy.revoke_api_key(platform, principal, key_id))
