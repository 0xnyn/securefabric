from fastapi import APIRouter

from securefabric_api.api import health
from securefabric_api.errors import ERROR_RESPONSES
from securefabric_api.routes import catalog, connect, connections, keys, me, organizations, status

v1_router = APIRouter(prefix="/v1", responses=ERROR_RESPONSES)
for sub in (
    me.router,
    keys.router,
    organizations.router,
    catalog.public,
    catalog.router,
    connections.router,
    connections.jobs_router,
    connect.router,
    connect.flow,
    status.router,
):
    v1_router.include_router(sub)


def _optional() -> None:
    """Routers whose domain modules land in later milestones register here."""
    import importlib

    for name in ("data", "events", "actions", "ops", "ingress", "admin"):
        try:
            mod = importlib.import_module(f"securefabric_api.routes.{name}")
        except ModuleNotFoundError as exc:
            if exc.name and exc.name.startswith("securefabric_api.routes"):
                continue
            raise
        for attr in ("router", "public"):
            if hasattr(mod, attr):
                v1_router.include_router(getattr(mod, attr))


_optional()

root_router = APIRouter()
root_router.include_router(health.router)
root_router.include_router(v1_router)
