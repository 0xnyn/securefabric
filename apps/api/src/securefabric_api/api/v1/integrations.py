"""Integrations: a provider enabled in an environment, with its models and schedule."""

from fastapi import APIRouter, Response, status

from securefabric_api.api.v1._util import no_content
from securefabric_api.dependencies import ConnDep
from securefabric_domain import service
from securefabric_domain.models import Created, IntegrationCreate, IntegrationPatch

router = APIRouter(prefix="/environments/{env}/integrations", tags=["integrations"])


@router.post("", name="enable_integration", status_code=status.HTTP_201_CREATED)
async def enable_integration(env: str, body: IntegrationCreate, conn: ConnDep) -> Created:
    return Created(id=await service.enable_integration(conn, env, body))


@router.patch("/{integration_id}", name="update_integration")
async def update_integration(
    env: str, integration_id: str, body: IntegrationPatch, conn: ConnDep
) -> Created:
    """Returns the integration's key, which changes on a rename (connections follow)."""
    return Created(id=await service.update_integration(conn, env, integration_id, body))


@router.delete(
    "/{integration_id}", name="delete_integration", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_integration(env: str, integration_id: str, conn: ConnDep) -> Response:
    await service.delete_integration(conn, env, integration_id)
    return no_content()
