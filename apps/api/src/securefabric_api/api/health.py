from typing import Literal

from fastapi import APIRouter, Response, status

from securefabric_api.dependencies import PoolDep, SettingsDep
from securefabric_api.schemas import ResponseModel
from securefabric_db import ping

router = APIRouter(prefix="/health", tags=["health"])


class Liveness(ResponseModel):
    status: Literal["ok"] = "ok"
    service: str
    environment: str


class Readiness(ResponseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, bool]


@router.get("/live", summary="Liveness probe")
async def live(settings: SettingsDep) -> Liveness:
    return Liveness(service=settings.service_name, environment=settings.environment)


@router.get(
    "/ready",
    summary="Readiness probe",
    responses={503: {"model": Readiness, "description": "A dependency is unavailable"}},
)
async def ready(pool: PoolDep, response: Response) -> Readiness:
    checks = {"database": await ping(pool)}
    ok = all(checks.values())
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Readiness(status="ok" if ok else "degraded", checks=checks)
