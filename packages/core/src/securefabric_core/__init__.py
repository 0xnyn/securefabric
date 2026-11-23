"""Shared building blocks for SecureFabric services."""

from securefabric_core.errors import (
    AppError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from securefabric_core.logging import configure_logging, get_logger
from securefabric_core.settings import BaseServiceSettings, Environment, LogFormat

__all__ = [
    "AppError",
    "BaseServiceSettings",
    "ConflictError",
    "Environment",
    "LogFormat",
    "NotFoundError",
    "PermissionDeniedError",
    "ValidationFailedError",
    "configure_logging",
    "get_logger",
]

__version__ = "0.1.0"
