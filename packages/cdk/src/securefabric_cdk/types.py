"""Value types shared by connectors and the engine."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from securefabric_schema import GrantStatus

type RawItem = dict[str, Any]
type Checkpoint = dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class Page:
    """One page from ``Stream.read``.

    ``checkpoint`` is the complete checkpoint value to save in the same
    transaction as this page's records. ``vendor_total`` is the vendor's own
    count of the full listing when it reports one: the sweep guard's vendor
    confirmation (part 4, section 8).
    """

    items: list[RawItem]
    checkpoint: Checkpoint = None
    vendor_total: int | None = None
    raw_page_id: str | None = None


@dataclass(frozen=True, slots=True)
class Skip:
    """``normalize`` decided this raw item is not a record (filtered, irrelevant)."""

    reason: str = ""


@dataclass(frozen=True, slots=True)
class Tombstone:
    """``normalize`` saw a vendor-reported deletion (``deletion: vendor_reported``).
    The platform marks the record DELETED; it never invents the state itself."""

    object: str  # "resource" | "vulnerability_finding"
    natural_key: str


@dataclass(frozen=True, slots=True)
class GoneMarker:
    """``read_one`` found that the record no longer exists at the vendor."""

    key: str


@dataclass(frozen=True, slots=True)
class VerifyResult:
    """What ``verify`` learned about the vendor tenant.

    ``tenant_identity`` feeds the duplicate-connection fingerprint (AUTH-10).
    ``config_updates`` is merged into ``connection_config`` (e.g. listing mode).
    """

    tenant_identity: str
    display_name: str | None = None
    config_updates: dict[str, Any] = field(default_factory=dict)
    vendor_tenant_ref: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Grant:
    status: GrantStatus
    endpoint: str | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizeContext:
    """Pure inputs for ``normalize``: no clock, no I/O."""

    options: dict[str, Any]
    config: dict[str, Any]
    stream: str


# ---------------------------------------------------------------- webhooks


@dataclass(frozen=True, slots=True)
class IngressDelivery:
    delivery_id: str
    event: str
    action: str | None
    payload: dict[str, Any]
    vendor_tenant_ref: str | None


@dataclass(frozen=True, slots=True)
class MarkDirty:
    stream: str
    key: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class TriggerStream:
    stream: str
    reason: str = ""
    full: bool = False  # a full pass, e.g. repositories added to an installation


@dataclass(frozen=True, slots=True)
class ConnectionRevoked:
    """The vendor revoked our access (uninstall, suspend)."""

    reason: str = ""
    suspended: bool = False


@dataclass(frozen=True, slots=True)
class ConnectionRestored:
    """Access came back (unsuspend): resume schedules and catch up."""

    reason: str = ""


@dataclass(frozen=True, slots=True)
class ReprobeGrants:
    reason: str = ""


@dataclass(frozen=True, slots=True)
class UpdateConfig:
    updates: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Ignore:
    reason: str = ""


type WebhookEffect = (
    MarkDirty
    | TriggerStream
    | ConnectionRevoked
    | ConnectionRestored
    | ReprobeGrants
    | UpdateConfig
    | Ignore
)


# ---------------------------------------------------------------- actions


@dataclass(frozen=True, slots=True)
class Action:
    name: str
    params: dict[str, Any]
    record: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ActionResult:
    status: Literal["SUCCEEDED", "FAILED"]
    vendor_response: dict[str, Any] = field(default_factory=dict)
    refetch: list[MarkDirty] = field(default_factory=list)
    message: str | None = None


# ---------------------------------------------------------------- auth plans


@dataclass(frozen=True, slots=True)
class AuthPlan:
    """How a connection authenticates, built by ``Connector.auth_plan``.

    Either static headers (API key, basic) or per-scheme exchanges that mint
    short-lived tokens (OAuth2 refresh, client credentials, GitHub installation
    tokens). The platform wraps exchanges in the shared refresh discipline.
    """

    static_headers: dict[str, str] | None = None
    exchanges: dict[str, Any] = field(
        default_factory=dict
    )  # scheme -> async (CachedToken|None) -> CachedToken
    margins_s: dict[str, int] = field(default_factory=dict)
    header_format: dict[str, str] = field(default_factory=dict)  # scheme -> "Bearer {token}" style


# ---------------------------------------------------------------- auth material


@dataclass(frozen=True, slots=True)
class AuthMaterial:
    """What a token provider hands the HTTP client. Never given to connector code."""

    headers: dict[str, str]
    expires_at: datetime | None = None
    fingerprint: str = ""
