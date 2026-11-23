"""RFC 9457 problem details for every error (API-06).

One format everywhere, including FastAPI's validation errors (Leen mixes two)::

    {"type": "https://docs.securefabric.dev/errors/scope_missing", "title": "Missing scope",
     "status": 403, "detail": "This key lacks provisioning:write.", "code": "scope_missing",
     "request_id": "req_...", "errors": [{"field": "...", "message": "..."}]}
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from securefabric_core import AppError, get_logger

log = get_logger(__name__)

ERRORS_BASE = "https://docs.securefabric.dev/errors/"
PROBLEM_JSON = "application/problem+json"


class FieldError(BaseModel):
    field: str
    message: str


class Problem(BaseModel):
    """The body of every non-2xx response."""

    type: str = Field(description="A URI identifying the problem type.")
    title: str
    status: int
    detail: str | None = None
    code: str = Field(description="Stable, machine-readable error code.")
    request_id: str | None = None
    errors: list[FieldError] = Field(default_factory=list)


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": Problem, "content": {PROBLEM_JSON: {}}, "description": desc}
    for code, desc in (
        (400, "Bad request"),
        (401, "Authentication required"),
        (403, "Permission denied"),
        (404, "Not found"),
        (409, "Conflicts with the current state"),
        (410, "Gone"),
        (422, "Validation failed"),
        (429, "Too many requests"),
        (500, "Unexpected server error"),
    )
}

_TITLES = {
    400: "Bad request",
    401: "Authentication required",
    403: "Permission denied",
    404: "Not found",
    405: "Method not allowed",
    409: "Conflict",
    410: "Gone",
    422: "Validation failed",
    429: "Too many requests",
    500: "Internal error",
    503: "Service unavailable",
}


def problem(
    request: Request | None,
    status_code: int,
    code: str,
    detail: str | None,
    *,
    title: str | None = None,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) if request is not None else None
    body = {
        "type": ERRORS_BASE + code,
        "title": title or _TITLES.get(status_code, "Error"),
        "status": status_code,
        "detail": detail,
        "code": code,
        "request_id": request_id,
        "errors": errors or [],
    }
    return JSONResponse(
        status_code=status_code, content=body, media_type=PROBLEM_JSON, headers=headers
    )


class IdempotentReplay(Exception):
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IdempotentReplay)
    async def _replay(_: Request, exc: IdempotentReplay) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=exc.body, headers={"Idempotent-Replayed": "true"}
        )

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            log.error("app_error", code=exc.error_code, message=exc.message)
        return problem(
            request,
            exc.status_code,
            exc.error_code,
            exc.message,
            title=exc.title,
            errors=exc.errors,
            headers=exc.headers or None,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(
            exc.status_code, f"http_{exc.status_code}"
        )
        return problem(
            request, exc.status_code, code, str(exc.detail), headers=getattr(exc, "headers", None)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(
                    str(p) for p in e["loc"] if p not in ("body", "query", "path", "header")
                )
                or "request",
                "message": e["msg"],
            }
            for e in exc.errors()
        ]
        return problem(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_failed",
            "Request validation failed",
            errors=errors,
        )

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", exc_type=type(exc).__name__)
        return problem(request, 500, "internal_error", "An unexpected error occurred")
