"""Transport-agnostic domain errors.

Services raise these from business logic; each app maps them to its own transport
(RFC 9457 problem details in the API, retry/dead-letter decisions in a worker).
``code`` is a stable machine-readable string (part 7, section 8).
"""

from typing import Any, ClassVar


class AppError(Exception):
    code: ClassVar[str] = "internal_error"
    status_code: ClassVar[int] = 500
    title: ClassVar[str] = "Internal error"

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        *,
        code: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
        **details: Any,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.errors = errors or []
        self.headers = headers or {}
        self._code = code

    @property
    def error_code(self) -> str:
        return self._code or self.code

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.error_code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class BadRequestError(AppError):
    code = "bad_request"
    status_code = 400
    title = "Bad request"


class UnauthenticatedError(AppError):
    code = "unauthenticated"
    status_code = 401
    title = "Authentication required"


class PermissionDeniedError(AppError):
    code = "permission_denied"
    status_code = 403
    title = "Permission denied"


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404
    title = "Not found"


class ConflictError(AppError):
    code = "conflict"
    status_code = 409
    title = "Conflict"


class GoneError(AppError):
    code = "gone"
    status_code = 410
    title = "Gone"


class ValidationFailedError(AppError):
    code = "validation_failed"
    status_code = 422
    title = "Validation failed"


class RateLimitedError(AppError):
    code = "rate_limited"
    status_code = 429
    title = "Too many requests"


class UnavailableError(AppError):
    code = "unavailable"
    status_code = 503
    title = "Service unavailable"
