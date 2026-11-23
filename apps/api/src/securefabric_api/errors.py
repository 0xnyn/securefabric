"""Map exceptions to a consistent JSON error envelope: ``{"error": {code, message, details?}}``.

The envelope is also declared as a schema (:class:`ErrorResponse`) and attached to
every route via :data:`ERROR_RESPONSES`, so the generated OpenAPI document (and the
TypeScript client built from it) types error bodies as precisely as success bodies.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from securefabric_api.schemas import ResponseModel
from securefabric_core import AppError, get_logger

log = get_logger(__name__)


class ErrorBody(BaseModel):
    # Plain BaseModel: the handlers omit `details` when empty, so it stays optional.
    code: str = Field(description="Stable, machine-readable error code, e.g. `not_found`.")
    message: str = Field(description="Human-readable summary. Safe to show to users.")
    details: dict[str, Any] | None = Field(
        default=None, description="Structured context, e.g. per-field validation errors."
    )


class ErrorResponse(ResponseModel):
    """The body of every non-2xx response."""

    error: ErrorBody


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Not found"},
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "Conflicts with the current state",
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorResponse,
        "description": "Request validation failed",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "model": ErrorResponse,
        "description": "Unexpected server error",
    },
}


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.to_dict()})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else f"http_{exc.status_code}"
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail)),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_envelope(
                "validation_failed",
                "Request validation failed",
                jsonable_encoder({"errors": exc.errors()}),
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_error(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", exc_type=type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope("internal_error", "An unexpected error occurred"),
        )
