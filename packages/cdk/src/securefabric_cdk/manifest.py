"""The connector manifest (docs/plan/05-connector-sdk.md, section 2).

``manifest.yaml`` is validated by this model (and the JSON Schema it exports, CDK-02).
The catalogue, the connect forms, the capabilities block and the docs are all
generated from it.
"""

from pathlib import Path
from typing import Any, Literal

import jsonschema
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from securefabric_schema import (
    AuthMode,
    ConnectStyle,
    DeletionMode,
    FindingType,
    ResourceType,
    SyncMode,
)


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OAuth2Config(_M):
    # Absolute, relative to the API base, or ``local:/path`` (served by the platform
    # through the connector's in-process vendor, e.g. SANDBOX). Client credentials
    # vendors have no authorize step.
    authorize_url: str | None = None
    token_url: str
    scopes: list[str] = Field(default_factory=list)
    pkce: bool = True
    single_use_refresh_tokens: bool = False


class AuthSpec(_M):
    mode: AuthMode
    vendor_app: Literal["required", "optional", "none"] = "none"
    connect: ConnectStyle = ConnectStyle.FORM
    oauth2: OAuth2Config | None = None
    token_refresh_margin_s: int = Field(default=900, ge=0)


class Region(_M):
    id: str
    api_base: str
    label: str | None = None


class BodyPattern(_M):
    status: int
    contains: str
    treat_as: Literal["rate_limited", "feature_not_enabled", "permission_missing"]


class RetrySpec(_M):
    statuses: list[int | str] = Field(default_factory=lambda: list[int | str]([429, "5xx"]))
    reset_header: str | None = None
    retry_after_header: str | None = "retry-after"
    remaining_header: str | None = None
    limit_header: str | None = None
    body_patterns: list[BodyPattern] = Field(default_factory=list)
    max_in_request_retries: int = Field(default=3, ge=0, le=10)

    def is_retryable_status(self, status: int) -> bool:
        for s in self.statuses:
            if isinstance(s, int) and s == status:
                return True
            if isinstance(s, str) and s.endswith("xx") and str(status)[0] == s[0]:
                return True
        return False


class BudgetSpec(_M):
    key: str = "{connection_id}"
    per_hour: int | None = None
    per_minute_points: int | None = None
    max_concurrency: int = Field(default=4, ge=1)
    max_requests_per_second: float = Field(default=10.0, gt=0)
    write_cost: int = Field(default=1, ge=1)


class HttpSpec(_M):
    default_headers: dict[str, str] = Field(default_factory=dict)
    retry: RetrySpec = Field(default_factory=RetrySpec)
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
    timeout_connect_s: float = 10.0
    timeout_read_s: float = 300.0


class Permission(_M):
    name: str
    access: Literal["read", "write"]
    streams: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    optional: bool = False


class Interval(_M):
    default: int = Field(ge=60)
    min: int = Field(ge=60)
    max: int = Field(ge=60)


class Capability(_M):
    supported: bool
    notes: str | None = None


class StreamSpec(_M):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    object: Literal["resource", "vulnerability_finding"]
    title: str | None = None
    finding_types: list[FindingType] = Field(default_factory=list)
    resource_types: list[ResourceType] = Field(default_factory=list)
    sync_mode: SyncMode
    interval: Interval
    full_every: int | None = Field(default=None, ge=3600)
    vendor_retention: int | None = None
    deletion: DeletionMode
    natural_key: str
    endpoint: str | None = None
    checkpoint_schema: dict[str, Any] | None = None
    webhook_events: list[str] = Field(default_factory=list)
    capabilities: dict[str, Capability] = Field(default_factory=dict)
    supports_targeted: bool = False
    depends_on: list[str] = Field(default_factory=list)
    enabled_by_default: bool = True
    min_vendor_version: str | None = None
    cost: str | None = None


class ActionSpec(_M):
    name: str
    object: Literal["resource", "vulnerability_finding"]
    requires_permission_tier: Literal["read", "read_write"] = "read_write"
    reasons: list[str] = Field(default_factory=list)


class WebhookSpec(_M):
    signature_header: str
    signature_prefix: str = ""
    algorithm: Literal["hmac-sha256"] = "hmac-sha256"
    delivery_id_header: str
    event_header: str
    tenant_ref_path: str
    action_path: str = "action"


class Manifest(_M):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    display_name: str
    description: str = ""
    categories: list[str]
    status: Literal["beta", "ga", "deprecated"]
    logo: str | None = None
    docs_url: str | None = None
    billing_exempt: bool = False
    api_version: str | None = None

    auth: AuthSpec
    connection_config: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )
    credentials: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )
    options: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    regions: list[Region] = Field(default_factory=list)
    http: HttpSpec = Field(default_factory=HttpSpec)
    permissions: list[Permission] = Field(default_factory=list)
    webhooks: WebhookSpec | None = None
    streams: list[StreamSpec]
    actions: list[ActionSpec] = Field(default_factory=list)
    scrub_fields: list[str] = Field(default_factory=list)
    passthrough_allowlist: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> "Manifest":
        names = [s.name for s in self.streams]
        if len(names) != len(set(names)):
            raise ValueError("stream names must be unique")
        for s in self.streams:
            iv = s.interval
            if not iv.min <= iv.default <= iv.max:
                raise ValueError(f"{s.name}: interval must satisfy min <= default <= max")
            if s.vendor_retention is not None and iv.default > s.vendor_retention:
                raise ValueError(f"{s.name}: default interval exceeds vendor retention (SYNC-18)")
            if s.sync_mode is SyncMode.FULL and s.deletion is DeletionMode.VENDOR_REPORTED:
                raise ValueError(f"{s.name}: a full stream must sweep or declare none")
            if s.object == "vulnerability_finding" and not s.finding_types:
                raise ValueError(f"{s.name}: finding streams declare finding_types")
            if s.object == "resource" and not s.resource_types:
                raise ValueError(f"{s.name}: resource streams declare resource_types")
            for dep in s.depends_on:
                if dep not in names:
                    raise ValueError(f"{s.name}: depends on unknown stream {dep}")
        action_names = {a.name for a in self.actions}
        for p in self.permissions:
            for ref in p.streams:
                if ref not in names:
                    raise ValueError(f"permission {p.name!r} references unknown stream {ref}")
            for ref in p.actions:
                if ref not in action_names:
                    raise ValueError(f"permission {p.name!r} references unknown action {ref}")
        if self.permissions:
            covered = {ref for p in self.permissions for ref in p.streams}
            missing = [n for n in names if n not in covered]
            if missing:
                raise ValueError(f"streams with no declared permission (SEC-09): {missing}")
        for label, schema in (
            ("connection_config", self.connection_config),
            ("credentials", self.credentials),
            ("options", self.options),
        ):
            try:
                jsonschema.Draft202012Validator.check_schema(schema)
            except jsonschema.SchemaError as exc:
                raise ValueError(f"{label} is not a valid JSON Schema: {exc.message}") from exc
        if self.auth.mode in (AuthMode.OAUTH2, AuthMode.OAUTH2_CC) and self.auth.oauth2 is None:
            raise ValueError(f"{self.auth.mode} auth needs an oauth2 block")
        if self.auth.mode is AuthMode.OAUTH2 and not (
            self.auth.oauth2 and self.auth.oauth2.authorize_url
        ):
            raise ValueError("OAUTH2 auth needs oauth2.authorize_url")
        # Option defaults must validate against the option schema.
        jsonschema.validate(option_defaults(self.options), self.options)
        return self

    # ------------------------------------------------------------ helpers

    def stream(self, name: str) -> StreamSpec:
        for s in self.streams:
            if s.name == name:
                return s
        raise KeyError(name)

    @property
    def stream_names(self) -> list[str]:
        return [s.name for s in self.streams]

    def default_streams(self) -> list[str]:
        return [s.name for s in self.streams if s.enabled_by_default]

    def secret_fields(self) -> list[str]:
        props: dict[str, Any] = self.credentials.get("properties", {})
        return [k for k, v in props.items() if v.get("x-secret") or v.get("secret")]

    def action(self, name: str) -> ActionSpec | None:
        return next((a for a in self.actions if a.name == name), None)


def option_defaults(schema: dict[str, Any]) -> dict[str, Any]:
    return {k: v["default"] for k, v in schema.get("properties", {}).items() if "default" in v}


PLATFORM_OPTIONS: dict[str, Any] = {
    "initial_lookback_days": {"type": "integer", "minimum": 1, "maximum": 3650},
    "severity_floor": {"enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "UNKNOWN"]},
    "external_use_only": {"type": "boolean"},
    "stream_intervals": {
        "type": "object",
        "additionalProperties": {"type": "integer", "minimum": 60},
    },
}


def options_schema(manifest: Manifest) -> dict[str, Any]:
    """The connector's option schema plus the platform-level options (CON-05)."""
    props = dict(manifest.options.get("properties", {}))
    props.update(PLATFORM_OPTIONS)
    return {"type": "object", "properties": props, "additionalProperties": False}


def validate_options(manifest: Manifest, options: dict[str, Any]) -> dict[str, Any]:
    """Validate and fill defaults. Raises ``jsonschema.ValidationError``."""
    merged = {**option_defaults(manifest.options), **options}
    jsonschema.validate(merged, options_schema(manifest))
    for stream, interval in (merged.get("stream_intervals") or {}).items():
        spec = manifest.stream(stream)
        if interval < spec.interval.min or interval > spec.interval.max:
            raise jsonschema.ValidationError(
                f"interval for {stream} must be between {spec.interval.min} and {spec.interval.max} seconds"
            )
        if spec.vendor_retention is not None and interval > spec.vendor_retention:
            raise jsonschema.ValidationError(
                f"interval for {stream} exceeds the vendor's {spec.vendor_retention}s retention (SYNC-18)"
            )
    return merged


def version_tuple(version: str) -> tuple[int, ...]:
    """``"3.10.2"`` → ``(3, 10, 2)``; non-numeric parts end the version (``3.8.0-rc1``)."""
    out: list[int] = []
    for part in str(version).strip().lstrip("vV").split("."):
        digits = ""
        for ch in part:
            if not ch.isdigit():
                break
            digits += ch
        if not digits:
            break
        out.append(int(digits))
        if len(digits) != len(part):
            break  # "0-rc1": the version ends here
    return tuple(out)


def version_at_least(actual: str | None, minimum: str | None) -> bool:
    """True when there is nothing to compare (cloud vendors report no version)."""
    if not actual or not minimum:
        return True
    return version_tuple(actual) >= version_tuple(minimum)


def load_manifest(path: Path) -> Manifest:
    return Manifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def manifest_json_schema() -> dict[str, Any]:
    return Manifest.model_json_schema()
