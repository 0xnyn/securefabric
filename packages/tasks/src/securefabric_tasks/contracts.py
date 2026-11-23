"""Task contracts: the params/result schemas and specs for every durable task.

Add a new task by defining its models and a ``TaskSpec`` here, then register a
handler for it in ``apps/worker``.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from securefabric_tasks.queues import Queue
from securefabric_tasks.spec import TaskSpec

TenantPlan = Literal["free", "pro", "enterprise"]


class ProvisionTenantParams(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(
        min_length=3, max_length=40, pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"
    )
    plan: TenantPlan = "free"
    admin_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    activation_delay_seconds: float = Field(
        default=0,
        ge=0,
        le=3600,
        description="Durable sleep before activation; demonstrates suspend/resume.",
    )


class ProvisionTenantResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    plan: TenantPlan
    resources: list[str]
    activated_at: datetime


PROVISION_TENANT = TaskSpec(
    name="provision-tenant",
    queue=Queue.DEFAULT,
    params_model=ProvisionTenantParams,
    result_model=ProvisionTenantResult,
    max_attempts=5,
    retry_strategy={"kind": "exponential", "base_seconds": 2, "factor": 2, "max_seconds": 300},
    description="Allocate resources for a tenant, wait, then activate it.",
)


class SyncConnectionParams(BaseModel):
    """Run one vendor sync for a connection. The API has already recorded the job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    connection_id: str = Field(min_length=1, max_length=64)
    job_id: str = Field(min_length=1, max_length=64)
    duration_seconds: float = Field(
        default=2.6, ge=0, le=3600, description="Simulated vendor sync time (durable sleep)."
    )


class SyncConnectionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: str
    status: Literal["SUCCESS", "FAILED", "skipped"]
    added: int = 0
    updated: int = 0
    deleted: int = 0


SYNC_CONNECTION = TaskSpec(
    name="sync-connection",
    queue=Queue.DEFAULT,
    params_model=SyncConnectionParams,
    result_model=SyncConnectionResult,
    max_attempts=3,
    retry_strategy={"kind": "exponential", "base_seconds": 1, "factor": 2, "max_seconds": 30},
    description="Pull a connection's records from the vendor and update its sync job.",
)

ALL_TASKS: tuple[TaskSpec[BaseModel, BaseModel], ...] = (PROVISION_TENANT, SYNC_CONNECTION)  # type: ignore[assignment]
