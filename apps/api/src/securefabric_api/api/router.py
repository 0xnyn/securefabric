from fastapi import APIRouter

from securefabric_api.api import health
from securefabric_api.api.v1 import (
    connections,
    environments,
    integrations,
    members,
    status,
    tasks,
    tenants,
    workspace,
)
from securefabric_api.errors import ERROR_RESPONSES

v1_router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
for sub in (
    workspace.router,
    environments.router,
    environments.keys,
    environments.webhooks,
    environments.variables,
    integrations.router,
    connections.router,
    connections.sessions,
    connections.operations,
    members.router,
    status.router,
    tenants.router,
    tasks.router,
):
    v1_router.include_router(sub)

root_router = APIRouter()
root_router.include_router(health.router)
root_router.include_router(v1_router)
