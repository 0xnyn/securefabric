"""Vendor ingress: signature-authenticated, not part of the public OpenAPI."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from securefabric_api.deps import PlatformDep
from securefabric_domain import ingress

router = APIRouter(prefix="/ingress", include_in_schema=False)


@router.post("/{connector}/{vendor_app_id}")
async def receive(
    connector: str, vendor_app_id: str, request: Request, platform: PlatformDep
) -> JSONResponse:
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    result = await ingress.receive(platform, connector, vendor_app_id, headers, body)
    return JSONResponse(result, status_code=202)
