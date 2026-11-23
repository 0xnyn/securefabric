"""Durable task contracts and Absurd wiring shared by SecureFabric services."""

from securefabric_tasks.contracts import (
    ALL_TASKS,
    PROVISION_TENANT,
    SYNC_CONNECTION,
    ProvisionTenantParams,
    ProvisionTenantResult,
    SyncConnectionParams,
    SyncConnectionResult,
)
from securefabric_tasks.queues import Queue
from securefabric_tasks.settings import AbsurdSettings
from securefabric_tasks.spec import TaskSpec, TypedHandler

__all__ = [
    "ALL_TASKS",
    "PROVISION_TENANT",
    "SYNC_CONNECTION",
    "AbsurdSettings",
    "ProvisionTenantParams",
    "ProvisionTenantResult",
    "Queue",
    "SyncConnectionParams",
    "SyncConnectionResult",
    "TaskSpec",
    "TypedHandler",
]
