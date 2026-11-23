"""Event envelope and catalogue (docs/plan/07-public-api-and-events.md, section 9)."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventType(StrEnum):
    CONNECTION_CREATE_SUCCEEDED = "connection.create.succeeded"
    CONNECTION_CREATE_FAILED = "connection.create.failed"
    CONNECTION_SYNC_SUCCEEDED = "connection.sync.succeeded"
    CONNECTION_SYNC_FAILED = "connection.sync.failed"
    CONNECTION_SYNC_UNAUTHORIZED = "connection.sync.unauthorized"
    SYNC_COMPLETED = "sync.completed"
    CONNECTION_HEALTH_CHANGED = "connection.health.changed"
    CONNECTION_PAUSED = "connection.paused"
    CONNECTION_RESUMED = "connection.resumed"
    CONNECTION_DELETED = "connection.deleted"
    ACTION_COMPLETED = "action.completed"
    ACTION_FAILED = "action.failed"
    WEBHOOK_PING = "webhook.ping"


# Reserved names (CDC-05): the outbox can carry them, nothing emits them yet.
RESERVED_EVENT_TYPES = frozenset(
    {
        "finding.created",
        "finding.updated",
        "finding.deleted",
        "resource.created",
        "resource.updated",
        "resource.deleted",
    }
)


class EventEnvelope(BaseModel):
    """HOOK-10. ``sequence`` increases strictly per connection (HOOK-11)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="evt_<uuid>")
    type: str
    created_at: datetime
    environment_id: str
    organization_id: str | None = None
    connection_id: str | None = None
    sequence: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)
