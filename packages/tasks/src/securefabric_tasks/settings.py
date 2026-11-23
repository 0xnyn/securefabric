from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from securefabric_tasks.queues import Queue


class AbsurdSettings(BaseSettings):
    """Absurd client defaults, read from ``ABSURD_*`` env vars."""

    model_config = SettingsConfigDict(
        env_prefix="ABSURD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    default_queue: str = Queue.DEFAULT
    default_max_attempts: int = Field(default=5, ge=1)
