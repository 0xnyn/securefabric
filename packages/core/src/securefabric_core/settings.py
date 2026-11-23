"""Base settings shared by every service in the monorepo.

Each service subclasses :class:`BaseServiceSettings` and sets its own ``env_prefix``
so variables never collide (e.g. ``API_PORT`` vs ``WORKER_PORT``).
"""

from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    CONSOLE = "console"
    JSON = "json"


class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    service_name: str = "securefabric"
    environment: Environment = Environment.LOCAL
    debug: bool = False

    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_format: LogFormat = LogFormat.CONSOLE

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION
