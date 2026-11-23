from pydantic import Field
from pydantic_settings import SettingsConfigDict

from securefabric_core import BaseServiceSettings
from securefabric_tasks import Queue


class WorkerSettings(BaseServiceSettings):
    """Worker settings, read from ``WORKER_*`` env vars (see ``.env.example``)."""

    model_config = SettingsConfigDict(env_prefix="WORKER_")

    service_name: str = "securefabric-worker"
    queue: Queue = Queue.DEFAULT
    worker_id: str | None = Field(default=None, description="Defaults to hostname:pid")
    concurrency: int = Field(default=4, ge=1, le=256)
    claim_timeout: int = Field(default=120, ge=5, description="Lease seconds per claim")
    poll_interval: float = Field(default=0.25, gt=0)

    # Queue bootstrap: create the queue (idempotent) and apply a retention policy.
    auto_create_queue: bool = True
    queue_cleanup_ttl: str | None = "30 days"
    queue_cleanup_limit: int | None = 1000
