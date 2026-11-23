from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.alert_out_severity import AlertOutSeverity

if TYPE_CHECKING:
    from ..models.alert_out_detail import AlertOutDetail


T = TypeVar("T", bound="AlertOut")


@_attrs_define
class AlertOut:
    """
    Attributes:
        id (UUID):
        name (str):
        severity (AlertOutSeverity):
        subject (None | str):
        detail (AlertOutDetail):
        runbook (None | str): Path under docs/runbooks
        raised_at (datetime.datetime):
        resolved_at (datetime.datetime | None):
    """

    id: UUID
    name: str
    severity: AlertOutSeverity
    subject: None | str
    detail: AlertOutDetail
    runbook: None | str
    raised_at: datetime.datetime
    resolved_at: datetime.datetime | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        name = self.name

        severity = self.severity.value

        subject: None | str
        subject = self.subject

        detail = self.detail.to_dict()

        runbook: None | str
        runbook = self.runbook

        raised_at = self.raised_at.isoformat()

        resolved_at: None | str
        if isinstance(self.resolved_at, datetime.datetime):
            resolved_at = self.resolved_at.isoformat()
        else:
            resolved_at = self.resolved_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "severity": severity,
                "subject": subject,
                "detail": detail,
                "runbook": runbook,
                "raised_at": raised_at,
                "resolved_at": resolved_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.alert_out_detail import AlertOutDetail  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        name = d.pop("name")

        severity = AlertOutSeverity(d.pop("severity"))

        def _parse_subject(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        subject = _parse_subject(d.pop("subject"))

        detail = AlertOutDetail.from_dict(d.pop("detail"))

        def _parse_runbook(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        runbook = _parse_runbook(d.pop("runbook"))

        raised_at = datetime.datetime.fromisoformat(d.pop("raised_at"))

        def _parse_resolved_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                resolved_at_type_0 = datetime.datetime.fromisoformat(data)

                return resolved_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        resolved_at = _parse_resolved_at(d.pop("resolved_at"))

        alert_out = cls(
            id=id,
            name=name,
            severity=severity,
            subject=subject,
            detail=detail,
            runbook=runbook,
            raised_at=raised_at,
            resolved_at=resolved_at,
        )

        alert_out.additional_properties = d
        return alert_out

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
