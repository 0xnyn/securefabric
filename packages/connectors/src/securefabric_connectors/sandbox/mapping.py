"""SANDBOX → canonical mapping tables, as data (NORM-04, NORM-10)."""

from securefabric_schema import (
    FindingState,
    FindingType,
    Reachability,
    ResourceState,
    ResourceType,
    Severity,
)

FINDING_TYPE = {
    "host_vuln": FindingType.HOST,
    "container_vuln": FindingType.CONTAINER,
    "package": FindingType.DEPENDENCY,
    "code": FindingType.CODE,
    "secret": FindingType.SECRET,
    "iac": FindingType.IAC,
    "domain": FindingType.DOMAIN,
    "misc": FindingType.UNKNOWN,
}

SEVERITY = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.INFO,
    "none": Severity.UNKNOWN,
}

STATE = {
    "open": FindingState.OPEN,
    "resolved": FindingState.CLOSED,
    "suppressed": FindingState.IGNORED,
}

REACHABILITY = {
    "yes": Reachability.REACHABLE,
    "maybe": Reachability.POTENTIALLY_REACHABLE,
    "no": Reachability.UNREACHABLE,
    "unknown": Reachability.UNKNOWN,
}

HOST_STATE = {"active": ResourceState.ACTIVE, "retired": ResourceState.INACTIVE}

ASSET_TYPE = {
    "host": ResourceType.HOST,
    "image": ResourceType.IMAGE,
    "container": ResourceType.CONTAINER,
}

# Write-back: canonical request → vendor status (part 7, section 7).
SET_STATE = {
    ("IGNORED", "false_positive"): "suppressed",
    ("IGNORED", "accepted_risk"): "suppressed",
    ("IGNORED", "test_code"): "suppressed",
    ("OPEN", None): "open",
    ("CLOSED", None): "resolved",
}
