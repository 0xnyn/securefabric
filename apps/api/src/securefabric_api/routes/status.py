"""System status (``make status`` and the dash's Status page report the same facts).

Readable without credentials, but then only the summary is returned; see
``securefabric_domain.status`` for what customers and operators additionally see.
"""

import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request

from securefabric_api import __version__
from securefabric_api.deps import PlatformDep, bearer_token, get_principal
from securefabric_api.schemas import ResponseModel, Timestamp
from securefabric_domain import status as svc

router = APIRouter(prefix="/status", tags=["status"])


class SystemStatus(ResponseModel):
    status: str
    problems: list[str]
    version: str
    uptime_seconds: float | None = None
    database: dict[str, Any]
    migrations: dict[str, Any]
    workers: list[dict[str, Any]]
    queues: list[dict[str, Any]]
    runs: dict[str, int]
    stuck_runs: int
    failed_runs_last_day: int
    alert_counts: dict[str, int]
    alerts: list[dict[str, Any]]
    checked_at: Timestamp


@router.get(
    "",
    name="get_status",
    summary="Database, migrations, workers, queues and alerts (summary only without credentials)",
)
async def get_status(platform: PlatformDep, request: Request) -> SystemStatus:
    audience: svc.Audience = "public"
    if bearer_token(request):
        principal = await get_principal(request, platform)  # bad credentials are still a 401
        audience = "operator" if principal.is_operator else "customer"
    try:
        async with platform.pool.connection(timeout=2) as conn:
            facts = await svc.collect(conn, version=__version__)
    except Exception as exc:  # any failure here is reported as "down"
        facts = svc.down(__version__, exc)
    started = getattr(request.app.state, "started_at", None)
    return SystemStatus(
        **svc.view(facts, audience),
        uptime_seconds=round(time.monotonic() - started, 1) if started else None,
        checked_at=datetime.now(UTC),
    )
