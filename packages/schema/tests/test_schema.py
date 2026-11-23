"""Canonical model invariants that every connector and the write path rely on."""

import pytest
from pydantic import ValidationError

from securefabric_schema import (
    RESERVED_EVENT_TYPES,
    EventType,
    FindingRecord,
    FindingState,
    FindingType,
    HealthCode,
    HealthStatus,
    ResolutionOwner,
    ResourceRecord,
    ResourceType,
    Severity,
)
from securefabric_schema.records import material


def test_severity_rank_is_a_total_order() -> None:
    ranks = [s.rank for s in Severity]
    assert sorted(ranks, reverse=True) == ranks == [5, 4, 3, 2, 1, 0]


def test_every_health_code_has_a_status_severity_and_description() -> None:
    severities = {c.severity for c in HealthCode}
    assert len(severities) == len(HealthCode), "roll-up needs a strict order"
    assert HealthCode.HEALTHY.severity == 0
    assert max(HealthCode, key=lambda c: c.severity) is HealthCode.REAUTHORIZATION_REQUIRED
    for code in HealthCode:
        assert code.description
        assert code.status is (
            HealthStatus.HEALTHY
            if code is HealthCode.HEALTHY
            else HealthStatus.INITIALIZING
            if code is HealthCode.INITIALIZING
            else HealthStatus.UNHEALTHY
        )
        # Every unhealthy code names who has to act (the dashboard shows it).
        assert (code.owner is None) == (code is HealthCode.HEALTHY)
    assert HealthCode.UNAUTHORIZED.owner is ResolutionOwner.CUSTOMER
    assert HealthCode.VENDOR_SERVER_ERROR.owner is ResolutionOwner.VENDOR


def _finding(**kw: object) -> FindingRecord:
    return FindingRecord.model_validate(
        {"natural_key": "alert/1", "type": FindingType.CODE, "state": "OPEN", **kw}
    )


@pytest.mark.parametrize("state", [FindingState.REOPENED, FindingState.DELETED])
def test_connectors_cannot_report_platform_derived_states(state: FindingState) -> None:
    with pytest.raises(ValidationError, match="derived by the platform"):
        _finding(state=state)


def test_cve_ids_are_normalised_and_deduplicated() -> None:
    assert _finding(cve_ids=[" cve-2024-1 ", "CVE-2024-1", "CVE-2023-9"]).cve_ids == [
        "CVE-2024-1",
        "CVE-2023-9",
    ]
    with pytest.raises(ValidationError, match="not a CVE id"):
        _finding(cve_ids=["GHSA-xxxx-yyyy-zzzz"])


def test_records_are_strict_and_natural_keys_bounded() -> None:
    with pytest.raises(ValidationError):
        _finding(unexpected_field=1)
    with pytest.raises(ValidationError):
        _finding(natural_key="")
    with pytest.raises(ValidationError):
        ResourceRecord(natural_key="x" * 10_000, type=ResourceType.REPOSITORY)


def test_material_hash_input_excludes_the_raw_vendor_payload() -> None:
    a = _finding(severity=Severity.HIGH, vendor_data={"etag": "1"})
    b = _finding(severity=Severity.HIGH, vendor_data={"etag": "2"})
    assert material(a) == material(b)
    assert "vendor_data" not in material(a)
    assert material(a) != material(_finding(severity=Severity.LOW))


def test_event_catalogue_does_not_overlap_reserved_names() -> None:
    assert not {e.value for e in EventType} & RESERVED_EVENT_TYPES
