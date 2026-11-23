from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Postgres connection settings, read from ``DATABASE_*`` env vars.

    Shared by every service so they all point at the same database.
    """

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    url: str = "postgresql://securefabric:securefabric@localhost:5432/securefabric"
    pool_min_size: int = Field(default=1, ge=0)
    pool_max_size: int = Field(default=10, ge=1)
    pool_timeout: float = Field(default=10.0, gt=0)
    connect_timeout: int = Field(default=5, ge=1)
