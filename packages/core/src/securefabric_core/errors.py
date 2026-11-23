"""Transport-agnostic domain errors.

Services raise these from business logic; each app maps them to its own transport
(HTTP status codes in the API, retry/dead-letter decisions in a worker, ...).
"""

from typing import Any, ClassVar


class AppError(Exception):
    code: ClassVar[str] = "internal_error"
    status_code: ClassVar[int] = 500

    def __init__(self, message: str = "An unexpected error occurred", **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class ConflictError(AppError):
    code = "conflict"
    status_code = 409


class PermissionDeniedError(AppError):
    code = "permission_denied"
    status_code = 403


class ValidationFailedError(AppError):
    code = "validation_failed"
    status_code = 422
