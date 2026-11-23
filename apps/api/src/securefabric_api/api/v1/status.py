"""System status for the dash's Status page (``make status`` reports the same)."""

from fastapi import APIRouter, Request

from securefabric_api import __version__
from securefabric_api.dependencies import PoolDep, SettingsDep
from securefabric_domain.status import SystemStatus, collect

router = APIRouter(prefix="/status", tags=["status"])


@router.get("", name="get_status", summary="Database, migrations, workers, queues, workspace")
async def get_status(pool: PoolDep, settings: SettingsDep, request: Request) -> SystemStatus:
    started = getattr(request.app.state, "started_at", None)
    try:
        async with pool.connection(timeout=2) as conn:
            return await collect(
                conn, version=__version__, environment=settings.environment, started_at=started
            )
    except Exception as exc:
        return await collect(
            None,
            version=__version__,
            environment=settings.environment,
            started_at=started,
            error=f"Postgres is unreachable ({type(exc).__name__})",
        )
