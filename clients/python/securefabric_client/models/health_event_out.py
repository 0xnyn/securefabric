from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.health_event_out_details_item import HealthEventOutDetailsItem


T = TypeVar("T", bound="HealthEventOut")


@_attrs_define
class HealthEventOut:
    """
    Attributes:
        from_code (None | str):
        to_code (str):
        details (list[HealthEventOutDetailsItem]):
        job_id (None | UUID):
        at (datetime.datetime):
    """

    from_code: None | str
    to_code: str
    details: list[HealthEventOutDetailsItem]
    job_id: None | UUID
    at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from_code: None | str
        from_code = self.from_code

        to_code = self.to_code

        details = []
        for details_item_data in self.details:
            details_item = details_item_data.to_dict()
            details.append(details_item)

        job_id: None | str
        if isinstance(self.job_id, UUID):
            job_id = str(self.job_id)
        else:
            job_id = self.job_id

        at = self.at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "from_code": from_code,
                "to_code": to_code,
                "details": details,
                "job_id": job_id,
                "at": at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.health_event_out_details_item import HealthEventOutDetailsItem  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_from_code(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        from_code = _parse_from_code(d.pop("from_code"))

        to_code = d.pop("to_code")

        details = []
        _details = d.pop("details")
        for details_item_data in _details:
            details_item = HealthEventOutDetailsItem.from_dict(details_item_data)

            details.append(details_item)

        def _parse_job_id(data: object) -> None | UUID:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                job_id_type_0 = UUID(data)

                return job_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        job_id = _parse_job_id(d.pop("job_id"))

        at = datetime.datetime.fromisoformat(d.pop("at"))

        health_event_out = cls(
            from_code=from_code,
            to_code=to_code,
            details=details,
            job_id=job_id,
            at=at,
        )

        health_event_out.additional_properties = d
        return health_event_out

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
