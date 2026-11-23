"""Control-plane schemas: exactly the shapes the dash renders.

Python names are snake_case; JSON is camelCase (``createdAt``), so the generated
TypeScript types line up with ``apps/dash/src/lib/types.ts``. Timestamps are Unix
epoch **milliseconds** (what the dash's date code consumes).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

# --- Enumerations (Literal → TS string unions) ---------------------------------

ModelKey = Literal[
    "vulnerabilities",
    "devices",
    "detections",
    "cloud-findings",
    "cloud-resources",
    "users",
    "groups",
    "code-findings",
    "repositories",
    "alerts",
    "tickets",
    "vendors",
    "controls",
    "email-threats",
    "indicators",
]
SyncFrequency = Literal["15m", "1h", "4h", "12h", "24h"]
HealthCode = Literal[
    "HEALTHY",
    "SYNCING",
    "UNAUTHORIZED",
    "RATE_LIMIT_EXCEEDED",
    "VENDOR_SERVER_ERROR",
    "EXECUTION_TIMEOUT",
    "PAUSED",
]
JobStatus = Literal["QUEUED", "RUNNING", "SUCCESS", "FAILED"]
JobType = Literal["INITIAL", "SCHEDULED", "ON_DEMAND"]
OperationType = Literal["auth", "sync", "api", "action", "proxy", "webhook"]
OperationStatus = Literal["success", "failed", "running", "warning"]
WebhookEvent = Literal[
    "connection.create.succeeded",
    "connection.create.failed",
    "connection.sync.succeeded",
    "connection.sync.failed",
    "connection.sync.unauthorized",
    "connection.deleted",
    "action.completed",
    "action.failed",
]
KeyScope = Literal[
    "data:read",
    "actions:write",
    "connections:write",
    "integrations:write",
    "webhooks:write",
    "keys:write",
]
Role = Literal["Full access", "Contributor", "Support"]
ConnectTheme = Literal["system", "light", "dark"]

ALL_KEY_SCOPES: tuple[KeyScope, ...] = (
    "data:read",
    "actions:write",
    "connections:write",
    "integrations:write",
    "webhooks:write",
    "keys:write",
)

SLUG_PATTERN = r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"


class Schema(BaseModel):
    """Response shapes. Defaulted fields are always sent, so they're required in TS."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        json_schema_serialization_defaults_required=True,
    )


class Input(BaseModel):
    """Request bodies: camelCase, unknown fields rejected."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


# --- Read models -----------------------------------------------------------------


class Team(Schema):
    name: str
    plan: str
    slug: str


class User(Schema):
    email: str
    name: str


class Member(Schema):
    email: str
    id: str
    joined_at: int | None
    name: str
    role: Role


class ApiKey(Schema):
    created_at: int
    created_by: str
    id: str
    is_default: bool = False
    last_used_at: int | None
    name: str
    preview: str
    scopes: list[KeyScope]


class Integration(Schema):
    allow_sandbox: bool
    created_at: int
    display_name: str
    id: str = Field(description="The unique key, used as integrationId in the API.")
    models: list[ModelKey]
    provider: str
    sync_frequency: SyncFrequency
    write_scopes: list[str]


class SyncJob(Schema):
    added: int
    deleted: int
    duration_ms: int | None
    failure_reason: str | None = None
    id: str
    started_at: int
    status: JobStatus
    type: JobType
    updated: int


class Customer(Schema):
    email: str
    end_user_id: str
    org_name: str


class Connection(Schema):
    counts: dict[ModelKey, int]
    created_at: int
    credentials: dict[str, str] = Field(description="Masked; sandbox connections have none.")
    customer: Customer
    domain: str
    frequency_override: SyncFrequency | None
    health: HealthCode
    id: str
    integration_id: str
    jobs: list[SyncJob] = Field(description="Newest first, at most 40.")
    last_sync_at: int | None
    metadata: dict[str, str]
    paused: bool
    provider: str
    sandbox: bool
    tags: dict[str, str]
    webhook_override: str | None


class Operation(Schema):
    action: str
    connection_id: str | None
    customer: str | None
    duration_ms: int
    id: str
    integration_id: str | None
    method: str | None = None
    path: str | None = None
    provider: str | None
    records: int | None = None
    started_at: int
    status: OperationStatus
    status_code: int | None = None
    type: OperationType


class Webhook(Schema):
    created_at: int
    description: str = ""
    disabled: bool = False
    events: list[WebhookEvent]
    id: str
    url: str


class EnvVariable(Schema):
    key: str
    secret: bool
    value: str


class ConnectSettings(Schema):
    brand_name: str
    hide_badge: bool
    theme: ConnectTheme


class EnvKeys(Schema):
    rotated_at: int
    secret: str = Field(description="The default key's full value, for samples and the playground.")


class Environment(Schema):
    api_keys: list[ApiKey]
    callback_url: str
    connect: ConnectSettings
    connections: list[Connection] = Field(description="Newest first.")
    created_at: int
    id: str
    integrations: list[Integration]
    is_production: bool
    keys: EnvKeys
    name: str
    operations: list[Operation] = Field(description="Newest first, at most 800.")
    slug: str
    variables: list[EnvVariable]
    webhook_secret: str
    webhooks: list[Webhook]


class Workspace(Schema):
    environments: list[Environment]
    members: list[Member]
    seeded_at: int
    team: Team
    user: User
    version: int


# --- Write models ------------------------------------------------------------------


class ConnectSettingsPatch(Input):
    brand_name: str | None = Field(default=None, max_length=80)
    hide_badge: bool | None = None
    theme: ConnectTheme | None = None


class EnvironmentCreate(Input):
    name: str = Field(min_length=1, max_length=60)
    slug: str = Field(default="", max_length=24)
    is_production: bool = False
    copy_from: str | None = None


class EnvironmentPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    is_production: bool | None = None
    callback_url: str | None = Field(default=None, max_length=2048)
    connect: ConnectSettingsPatch | None = None


class ApiKeyCreate(Input):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[KeyScope] = Field(min_length=1)


class ApiKeyPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    scopes: list[KeyScope] | None = Field(default=None, min_length=1)


class ApiKeySecret(Schema):
    """A key's full value. Returned once, on create and roll, and never stored."""

    key: ApiKey
    secret: str


class WebhookCreate(Input):
    url: str = Field(min_length=1, max_length=2048)
    events: list[WebhookEvent] = Field(min_length=1)
    description: str = Field(default="", max_length=200)


class WebhookPatch(Input):
    url: str | None = Field(default=None, min_length=1, max_length=2048)
    events: list[WebhookEvent] | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, max_length=200)
    disabled: bool | None = None


class WebhookDelivery(Input):
    event: WebhookEvent | Literal["ping"]
    connection_id: str | None = None


class VariableSet(Input):
    value: str = Field(max_length=4096)
    secret: bool = False


class IntegrationCreate(Input):
    provider: str
    id: str | None = Field(default=None, max_length=60, pattern=SLUG_PATTERN)
    display_name: str | None = Field(default=None, max_length=80)
    models: list[ModelKey] | None = None
    sync_frequency: SyncFrequency = "1h"
    write_scopes: list[str] = Field(default_factory=list)
    allow_sandbox: bool | None = None


class IntegrationPatch(Input):
    id: str | None = Field(default=None, max_length=60, pattern=SLUG_PATTERN)
    display_name: str | None = Field(default=None, max_length=80)
    models: list[ModelKey] | None = None
    sync_frequency: SyncFrequency | None = None
    write_scopes: list[str] | None = None
    allow_sandbox: bool | None = None


class CustomerInput(Input):
    email: str = Field(max_length=254)
    end_user_id: str = Field(min_length=1, max_length=120)
    org_name: str = Field(min_length=1, max_length=120)


class ConnectionCreate(Input):
    integration_id: str
    customer: CustomerInput
    sandbox: bool = False
    credentials: dict[str, str] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)


class ConnectionPatch(Input):
    paused: bool | None = None
    frequency_override: SyncFrequency | None = None
    webhook_override: str | None = None
    tags: dict[str, str] | None = None
    metadata: dict[str, str] | None = None


class CredentialsUpdate(Input):
    values: dict[str, str]


class HealthSimulation(Input):
    health: HealthCode


class ConnectSessionCreate(Input):
    customer: CustomerInput
    integrations: list[str] = Field(default_factory=list)


class ConnectSession(Schema):
    expires_at: int
    token: str
    url: str


class OperationCreate(Input):
    """An operation the dash records itself, e.g. a playground request."""

    connection_id: str | None = None
    type: OperationType
    action: str = Field(min_length=1, max_length=300)
    status: OperationStatus
    duration_ms: int = Field(ge=0)
    method: str | None = None
    path: str | None = Field(default=None, max_length=2048)
    records: int | None = Field(default=None, ge=0)
    status_code: int | None = Field(default=None, ge=100, le=599)
    started_at: int | None = None


class MemberInvite(Input):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    role: Role


class MemberPatch(Input):
    role: Role


class SyncStarted(Schema):
    """A sync that started; the worker finishes it as a durable task."""

    connection_id: str
    job_id: str
    task_id: str | None = Field(description="The Absurd task running it, if one was spawned.")


class Created(Schema):
    id: str
