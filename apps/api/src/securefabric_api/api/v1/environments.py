"""Environments and what's scoped to one: API keys, webhooks, variables."""

from fastapi import APIRouter, Response, status

from securefabric_api.api.v1._util import no_content
from securefabric_api.dependencies import ConnDep
from securefabric_domain import service
from securefabric_domain.models import (
    ApiKeyCreate,
    ApiKeyPatch,
    ApiKeySecret,
    Created,
    EnvironmentCreate,
    EnvironmentPatch,
    VariableSet,
    WebhookCreate,
    WebhookDelivery,
    WebhookPatch,
)

router = APIRouter(prefix="/environments", tags=["environments"])
keys = APIRouter(prefix="/environments/{env}/keys", tags=["keys"])
webhooks = APIRouter(prefix="/environments/{env}/webhooks", tags=["webhooks"])
variables = APIRouter(prefix="/environments/{env}/variables", tags=["variables"])


@router.post("", name="create_environment", status_code=status.HTTP_201_CREATED)
async def create_environment(body: EnvironmentCreate, conn: ConnDep) -> Created:
    """Create an environment, optionally copying integrations and variables from another."""
    return Created(id=await service.create_environment(conn, body))


@router.patch("/{env}", name="update_environment", status_code=status.HTTP_204_NO_CONTENT)
async def update_environment(env: str, body: EnvironmentPatch, conn: ConnDep) -> Response:
    await service.update_environment(conn, env, body)
    return no_content()


@router.delete("/{env}", name="delete_environment", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(env: str, conn: ConnDep) -> Response:
    await service.delete_environment(conn, env)
    return no_content()


@router.post(
    "/{env}/webhook-secret/rotate",
    name="rotate_webhook_secret",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def rotate_webhook_secret(env: str, conn: ConnDep) -> Response:
    await service.rotate_webhook_secret(conn, env)
    return no_content()


# --- API keys --------------------------------------------------------------------


@keys.post("", name="create_api_key", status_code=status.HTTP_201_CREATED)
async def create_api_key(env: str, body: ApiKeyCreate, conn: ConnDep) -> ApiKeySecret:
    """Create a key. The secret is returned once and only its hash is kept."""
    return await service.create_api_key(conn, env, body)


@keys.patch("/{key_id}", name="update_api_key", status_code=status.HTTP_204_NO_CONTENT)
async def update_api_key(env: str, key_id: str, body: ApiKeyPatch, conn: ConnDep) -> Response:
    await service.update_api_key(conn, env, key_id, body)
    return no_content()


@keys.post("/{key_id}/roll", name="roll_api_key")
async def roll_api_key(env: str, key_id: str, conn: ConnDep) -> ApiKeySecret:
    return await service.roll_api_key(conn, env, key_id)


@keys.delete("/{key_id}", name="revoke_api_key", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(env: str, key_id: str, conn: ConnDep) -> Response:
    await service.revoke_api_key(conn, env, key_id)
    return no_content()


# --- Webhooks ----------------------------------------------------------------------


@webhooks.post("", name="add_webhook", status_code=status.HTTP_201_CREATED)
async def add_webhook(env: str, body: WebhookCreate, conn: ConnDep) -> Created:
    return Created(id=await service.add_webhook(conn, env, body))


@webhooks.patch("/{webhook_id}", name="update_webhook", status_code=status.HTTP_204_NO_CONTENT)
async def update_webhook(env: str, webhook_id: str, body: WebhookPatch, conn: ConnDep) -> Response:
    await service.update_webhook(conn, env, webhook_id, body)
    return no_content()


@webhooks.delete("/{webhook_id}", name="remove_webhook", status_code=status.HTTP_204_NO_CONTENT)
async def remove_webhook(env: str, webhook_id: str, conn: ConnDep) -> Response:
    await service.remove_webhook(conn, env, webhook_id)
    return no_content()


@webhooks.post(
    "/{webhook_id}/deliveries", name="deliver_webhook", status_code=status.HTTP_201_CREATED
)
async def deliver_webhook(
    env: str, webhook_id: str, body: WebhookDelivery, conn: ConnDep
) -> Created:
    """Send one event to one endpoint now (a test event or a resend)."""
    return Created(id=await service.deliver_webhook(conn, env, webhook_id, body))


# --- Variables ---------------------------------------------------------------------


@variables.put("/{key}", name="set_variable", status_code=status.HTTP_204_NO_CONTENT)
async def set_variable(env: str, key: str, body: VariableSet, conn: ConnDep) -> Response:
    await service.set_variable(conn, env, key, body)
    return no_content()


@variables.delete("/{key}", name="remove_variable", status_code=status.HTTP_204_NO_CONTENT)
async def remove_variable(env: str, key: str, conn: ConnDep) -> Response:
    await service.remove_variable(conn, env, key)
    return no_content()
