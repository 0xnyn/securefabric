"""Canonical enumerations (docs/plan/02-data-model.md, 03 section 7, 04).

Values are Leen V2 compatible where Leen defines them (PD-9). Enumerations are
open on the wire: clients must tolerate values they do not know.
"""

from enum import StrEnum


class ResourceType(StrEnum):
    BRANCH = "BRANCH"
    HOST = "HOST"
    CONTAINER = "CONTAINER"
    DEPENDENCY = "DEPENDENCY"
    IMAGE = "IMAGE"
    REPOSITORY = "REPOSITORY"
    VENDOR = "VENDOR"
    KUBERNETES = "KUBERNETES"
    FUNCTION = "FUNCTION"
    SOFTWARE = "SOFTWARE"
    UNKNOWN = "UNKNOWN"


class ResourceState(StrEnum):
    ACTIVE = "ACTIVE"
    IGNORED = "IGNORED"
    DELETED = "DELETED"
    INACTIVE = "INACTIVE"
    QUARANTINED = "QUARANTINED"
    UNKNOWN = "UNKNOWN"


class FindingType(StrEnum):
    DEPENDENCY = "DEPENDENCY"
    CODE = "CODE"
    SECRET = "SECRET"  # noqa: S105
    CONTAINER = "CONTAINER"
    IAC = "IAC"
    HOST = "HOST"
    DOMAIN = "DOMAIN"
    UNKNOWN = "UNKNOWN"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"
    UNKNOWN = "UNKNOWN"

    @property
    def rank(self) -> int:
        """5 (critical) to 0 (unknown): sorting by severity is an index order."""
        return _SEVERITY_RANK[self]


_SEVERITY_RANK = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
    Severity.UNKNOWN: 0,
}


class FindingState(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"
    IGNORED = "IGNORED"
    DELETED = "DELETED"
    UNKNOWN = "UNKNOWN"


OPEN_STATES = frozenset({FindingState.OPEN, FindingState.REOPENED})
NON_OPEN_STATES = frozenset({FindingState.CLOSED, FindingState.IGNORED})


class Reachability(StrEnum):
    REACHABLE = "REACHABLE"
    POTENTIALLY_REACHABLE = "POTENTIALLY_REACHABLE"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"


class ObjectType(StrEnum):
    RESOURCE = "resource"
    VULNERABILITY_FINDING = "vulnerability_finding"


class ConnectionState(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    HARD_DELETED = "HARD_DELETED"


class HealthStatus(StrEnum):
    INITIALIZING = "INITIALIZING"
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"


class ResolutionOwner(StrEnum):
    PLATFORM = "PLATFORM"
    CUSTOMER = "CUSTOMER"
    VENDOR = "VENDOR"


class HealthCode(StrEnum):
    INITIALIZING = "INITIALIZING"
    HEALTHY = "HEALTHY"
    UNAUTHORIZED = "UNAUTHORIZED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    VENDOR_CLIENT_ERROR = "VENDOR_CLIENT_ERROR"
    VENDOR_SERVER_ERROR = "VENDOR_SERVER_ERROR"
    EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    REAUTHORIZATION_REQUIRED = "REAUTHORIZATION_REQUIRED"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    @property
    def status(self) -> HealthStatus:
        if self is HealthCode.INITIALIZING:
            return HealthStatus.INITIALIZING
        if self is HealthCode.HEALTHY:
            return HealthStatus.HEALTHY
        return HealthStatus.UNHEALTHY

    @property
    def owner(self) -> ResolutionOwner | None:
        return _HEALTH_OWNER.get(self)

    @property
    def severity(self) -> int:
        """Fixed order for the connection roll-up: the worst code wins."""
        return _HEALTH_SEVERITY[self]

    @property
    def description(self) -> str:
        return _HEALTH_DESCRIPTION[self]


_HEALTH_OWNER = {
    HealthCode.INITIALIZING: ResolutionOwner.PLATFORM,
    HealthCode.UNAUTHORIZED: ResolutionOwner.CUSTOMER,
    HealthCode.RATE_LIMIT_EXCEEDED: ResolutionOwner.VENDOR,
    HealthCode.VENDOR_CLIENT_ERROR: ResolutionOwner.CUSTOMER,
    HealthCode.VENDOR_SERVER_ERROR: ResolutionOwner.VENDOR,
    HealthCode.EXECUTION_TIMEOUT: ResolutionOwner.PLATFORM,
    HealthCode.CONFIGURATION_ERROR: ResolutionOwner.CUSTOMER,
    HealthCode.REAUTHORIZATION_REQUIRED: ResolutionOwner.CUSTOMER,
    HealthCode.INTERNAL_ERROR: ResolutionOwner.PLATFORM,
}

_HEALTH_SEVERITY = {
    HealthCode.HEALTHY: 0,
    HealthCode.INITIALIZING: 1,
    HealthCode.RATE_LIMIT_EXCEEDED: 2,
    HealthCode.EXECUTION_TIMEOUT: 3,
    HealthCode.VENDOR_SERVER_ERROR: 4,
    HealthCode.VENDOR_CLIENT_ERROR: 5,
    HealthCode.INTERNAL_ERROR: 6,
    HealthCode.CONFIGURATION_ERROR: 7,
    HealthCode.UNAUTHORIZED: 8,
    HealthCode.REAUTHORIZATION_REQUIRED: 9,
}

_HEALTH_DESCRIPTION = {
    HealthCode.INITIALIZING: "The first sync has not completed yet.",
    HealthCode.HEALTHY: "Every enabled stream synced successfully.",
    HealthCode.UNAUTHORIZED: "The vendor rejected the credentials or a required permission is missing.",
    HealthCode.RATE_LIMIT_EXCEEDED: "Vendor rate limits stopped a sync from finishing in time.",
    HealthCode.VENDOR_CLIENT_ERROR: "The vendor rejected a request.",
    HealthCode.VENDOR_SERVER_ERROR: "The vendor returned server errors after all retries.",
    HealthCode.EXECUTION_TIMEOUT: "A sync exceeded its deadline.",
    HealthCode.CONFIGURATION_ERROR: "The connection's options or base URL are invalid.",
    HealthCode.REAUTHORIZATION_REQUIRED: "Token refresh keeps failing. Re-authorize the connection.",
    HealthCode.INTERNAL_ERROR: "An internal error occurred. SecureFabric has been alerted.",
}


class GrantStatus(StrEnum):
    GRANTED = "GRANTED"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_ENABLED = "NOT_ENABLED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class JobType(StrEnum):
    INITIAL = "INITIAL"
    SCHEDULED = "SCHEDULED"
    ON_DEMAND = "ON_DEMAND"
    WEBHOOK = "WEBHOOK"
    RETRY = "RETRY"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunState(StrEnum):
    QUEUED = "QUEUED"
    ADMITTED = "ADMITTED"
    RUNNING = "RUNNING"
    PARKED = "PARKED"
    RETRY_WAIT = "RETRY_WAIT"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


ACTIVE_RUN_STATES = frozenset(
    {RunState.QUEUED, RunState.ADMITTED, RunState.RUNNING, RunState.PARKED, RunState.RETRY_WAIT}
)
TERMINAL_RUN_STATES = frozenset(
    {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED, RunState.EXPIRED}
)


class Mode(StrEnum):
    BACKFILL = "backfill"
    INCREMENTAL = "incremental"
    FULL = "full"
    TARGETED = "targeted"


class SyncMode(StrEnum):
    INCREMENTAL = "incremental"
    FULL = "full"
    EXPORT = "export"


class DeletionMode(StrEnum):
    VENDOR_REPORTED = "vendor_reported"
    SWEEP = "sweep"
    NONE = "none"


class AuthMode(StrEnum):
    APP = "APP"
    API_KEY = "API_KEY"
    BASIC = "BASIC"
    OAUTH2 = "OAUTH2"
    OAUTH2_CC = "OAUTH2_CC"
    AWS_ROLE = "AWS_ROLE"


class ConnectStyle(StrEnum):
    REDIRECT = "redirect"
    FORM = "form"
