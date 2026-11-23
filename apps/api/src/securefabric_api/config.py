from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from securefabric_core import BaseServiceSettings


class ApiSettings(BaseServiceSettings):
    """API settings, read from ``API_*`` env vars (see ``.env.example``)."""

    model_config = SettingsConfigDict(env_prefix="API_")

    service_name: str = "securefabric-api"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    workers: int = Field(default=1, ge=1)
    reload: bool = False
    root_path: str = ""
    docs_enabled: bool = True
    cors_origins: list[str] = Field(default_factory=list)


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()
