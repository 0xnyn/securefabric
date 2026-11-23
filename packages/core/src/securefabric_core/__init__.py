"""Shared building blocks for SecureFabric services."""

from securefabric_core.errors import (
    AppError,
    BadRequestError,
    ConflictError,
    GoneError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitedError,
    UnauthenticatedError,
    UnavailableError,
    ValidationFailedError,
)
from securefabric_core.logging import configure_logging, get_logger
from securefabric_core.settings import BaseServiceSettings, Environment, LogFormat

__all__ = [
    "AppError",
    "BadRequestError",
    "BaseServiceSettings",
    "ConflictError",
    "Environment",
    "GoneError",
    "LogFormat",
    "NotFoundError",
    "PermissionDeniedError",
    "RateLimitedError",
    "UnauthenticatedError",
    "UnavailableError",
    "ValidationFailedError",
    "configure_logging",
    "get_logger",
]

__version__ = "0.1.0"
