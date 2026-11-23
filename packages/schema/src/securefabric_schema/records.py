"""Canonical records: what a connector's pure ``normalize`` returns.

These are the internal shapes the write path stores (docs/plan/02-data-model.md,
section 4). The public Leen V2 rendering is in :mod:`securefabric_schema.public`.

Platform-derived fields (ids, hashes, ``REOPENED``, ``state_updated_at`` fallback,
``first_seen``, stub resources, severity floor) are deliberately *absent* here:
connectors that reimplement them diverge (part 5, section 3).
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from securefabric_schema.enums import (
    FindingState,
    FindingType,
    Reachability,
    ResourceState,
    ResourceType,
    Severity,
)

NATURAL_KEY_MAX = 512


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


# ---------------------------------------------------------------- shared blocks
# Shapes and field names follow Leen V2 (docs.leen.dev/openapi_v2.json, PD-9).
# Anything not in Leen is marked "additive".


class Group(_Strict):
    uid: str | None = None
    name: str | None = None


class Tag(_Strict):
    key: str
    value: str | None = None
    source: str | None = None


class CvssScore(_Strict):
    version: str
    score: float
    vector: str
    severity: str | None = None


class Reference(_Strict):
    url: str
    source: str | None = None
    tags: list[str] = Field(default_factory=list)


class Vulnerability(_Strict):
    """One vendor-supplied vulnerability entry (Leen ``VulnCveRespModel``)."""

    uid: str
    description: str | None = None
    published: datetime | None = None
    last_modified: datetime | None = None
    source_identifier: str | None = None
    status: str | None = None
    weaknesses: list[str] = Field(default_factory=list)
    cvss_scores: list[CvssScore] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)


class Analytic(_Strict):
    uid: str | None = None
    name: str | None = None
    type: str | None = None
    url: str | None = None


class Product(_Strict):
    name: str | None = None
    vendor_name: str | None = None


class Ticket(_Strict):
    uid: str | None = None
    url: str | None = None
    status: str | None = None


class AffectedCode(_Strict):
    file_path: str | None = None
    start_line_number: int | None = None
    end_line_number: int | None = None
    url: str | None = None


class AffectedPackage(_Strict):
    name: str | None = None
    version: str | None = None
    package_manager: str | None = None
    reachability: Reachability | None = None
    fixed_version: str | None = None  # additive
    path: str | None = None  # additive: manifest or lock file path


class ResourceRelated(_Strict):
    affected_code: AffectedCode | None = None
    affected_package: AffectedPackage | None = None
    affected_image: str | None = None
    affected_os: str | None = None
    affected_platform: str | None = None
    port: int | None = None
    protocol: str | None = None
    service: str | None = None


class VulnerabilityIdentifier(_Strict):
    type: str  # CVE | CWE | GHSA | OWASP | OTHER
    value: str


class VendorAttributes(_Strict):
    id: str | None = None
    url: str | None = None
    severity: str | None = None
    state: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    vulnerability_identifiers: list[VulnerabilityIdentifier] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class ResourceRef(_Strict):
    """A finding's link to a resource, by the resource's natural key.

    ``type`` and ``name`` let the platform create a stub resource when the
    finding arrives before its resource (NORM-14).
    """

    natural_key: str = Field(min_length=1, max_length=NATURAL_KEY_MAX)
    type: ResourceType
    role: Literal["primary", "related"] = "primary"
    name: str | None = None
    stream: str | None = None


# ---------------------------------------------------------------- records


class ResourceRecord(_Strict):
    object: Literal["resource"] = "resource"
    natural_key: str = Field(min_length=1, max_length=NATURAL_KEY_MAX)
    type: ResourceType
    state: ResourceState = ResourceState.ACTIVE
    name: str | None = None
    url: str | None = None
    groups: list[Group] = Field(default_factory=list)
    tags: list[Tag] = Field(default_factory=list)
    # Leen's flat data union (branch: code_repo/repo_branch_name, host: hostnames...),
    # plus additive keys for types Leen has no shape for (repositories).
    data: dict[str, Any] = Field(default_factory=dict)
    cloud_metadata: dict[str, Any] | None = None
    vendor_id: str | None = None
    vendor_attributes_data: dict[str, Any] = Field(default_factory=dict)
    meta_derived: list[str] = Field(default_factory=list)
    # Raw vendor payload (already scrubbed by the connector). Not hashed (PD-12).
    vendor_data: dict[str, Any] | None = None


class FindingRecord(_Strict):
    object: Literal["vulnerability_finding"] = "vulnerability_finding"
    natural_key: str = Field(min_length=1, max_length=NATURAL_KEY_MAX)
    type: FindingType
    title: str | None = None
    description: str | None = None
    severity: Severity = Severity.UNKNOWN
    # The vendor's *current* state. REOPENED is derived by the platform.
    state: FindingState
    # The vendor's timestamp for the current state, when the connector trusts it.
    state_changed_at: datetime | None = None
    has_fix: bool | None = None
    exploitable: bool | None = None
    reachability: Reachability | None = None
    remediation: str | None = None
    analytic: Analytic | None = None
    analytic_output: str | None = None
    product: Product | None = None
    ticket: Ticket | None = None
    resource_related: list[ResourceRelated] = Field(default_factory=list)
    vulnerabilities: list[Vulnerability] = Field(default_factory=list)
    cve_ids: list[str] = Field(default_factory=list)
    meta_derived: list[str] = Field(default_factory=list)
    vendor: VendorAttributes = Field(default_factory=VendorAttributes)
    resources: list[ResourceRef] = Field(default_factory=list)
    vendor_data: dict[str, Any] | None = None

    @field_validator("state")
    @classmethod
    def _no_platform_states(cls, v: FindingState) -> FindingState:
        if v in (FindingState.REOPENED, FindingState.DELETED):
            raise ValueError(f"{v} is derived by the platform, a connector cannot report it")
        return v

    @field_validator("cve_ids")
    @classmethod
    def _cves_upper(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for cve in v:
            up = cve.strip().upper()
            if not up.startswith("CVE-"):
                raise ValueError(f"not a CVE id: {cve!r}")
            if up not in out:
                out.append(up)
        return out


type Record = ResourceRecord | FindingRecord


def material(record: Record) -> dict[str, Any]:
    """The fields that make up the material hash: everything canonical except the
    raw vendor payload (PD-12). Observational fields are not on the record."""
    return record.model_dump(mode="json", exclude={"vendor_data"})
