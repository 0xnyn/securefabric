from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.summary_by_severity import SummaryBySeverity
    from ..models.summary_by_state import SummaryByState
    from ..models.summary_by_type import SummaryByType
    from ..models.summary_open_by_severity import SummaryOpenBySeverity


T = TypeVar("T", bound="Summary")


@_attrs_define
class Summary:
    """
    Attributes:
        total (int):
        by_severity (SummaryBySeverity):
        by_state (SummaryByState):
        by_type (SummaryByType):
        open_by_severity (SummaryOpenBySeverity):
    """

    total: int
    by_severity: SummaryBySeverity
    by_state: SummaryByState
    by_type: SummaryByType
    open_by_severity: SummaryOpenBySeverity
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        total = self.total

        by_severity = self.by_severity.to_dict()

        by_state = self.by_state.to_dict()

        by_type = self.by_type.to_dict()

        open_by_severity = self.open_by_severity.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "total": total,
                "by_severity": by_severity,
                "by_state": by_state,
                "by_type": by_type,
                "open_by_severity": open_by_severity,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.summary_by_severity import SummaryBySeverity  # noqa: PLC0415
        from ..models.summary_by_state import SummaryByState  # noqa: PLC0415
        from ..models.summary_by_type import SummaryByType  # noqa: PLC0415
        from ..models.summary_open_by_severity import SummaryOpenBySeverity  # noqa: PLC0415

        d = dict(src_dict)
        total = d.pop("total")

        by_severity = SummaryBySeverity.from_dict(d.pop("by_severity"))

        by_state = SummaryByState.from_dict(d.pop("by_state"))

        by_type = SummaryByType.from_dict(d.pop("by_type"))

        open_by_severity = SummaryOpenBySeverity.from_dict(d.pop("open_by_severity"))

        summary = cls(
            total=total,
            by_severity=by_severity,
            by_state=by_state,
            by_type=by_type,
            open_by_severity=open_by_severity,
        )

        summary.additional_properties = d
        return summary

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
