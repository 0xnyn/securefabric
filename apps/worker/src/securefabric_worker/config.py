from pydantic import Field
from pydantic_settings import SettingsConfigDict

from securefabric_core import BaseServiceSettings


class WorkerSettings(BaseServiceSettings):
    """Worker settings, read from ``WORKER_*`` env vars (see ``.env.example``)."""

    model_config = SettingsConfigDict(env_prefix="WORKER_")

    service_name: str = "securefabric-worker"
    role: str = Field(
        default="all", description="scheduler | sync | control | delivery | maintenance | all"
    )
    worker_id: str | None = Field(default=None, description="Defaults to hostname:pid")
    concurrency: int = Field(default=4, ge=1, le=256)
    # Part 4, section 5: a dead worker's run resumes within 6 minutes.
    claim_timeout: int = Field(default=300, ge=5, description="Lease seconds per claim")
    poll_interval: float = Field(default=0.25, gt=0)
    scheduler_interval: float = Field(default=1.0, gt=0)
