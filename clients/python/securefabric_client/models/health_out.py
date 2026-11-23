from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.health_out_details_type_0_item import HealthOutDetailsType0Item


T = TypeVar("T", bound="HealthOut")


@_attrs_define
class HealthOut:
    """
    Attributes:
        name (str):
        status (str):
        description (None | str):
        resolution_owner (None | str):
        details (list[HealthOutDetailsType0Item] | None):
    """

    name: str
    status: str
    description: None | str
    resolution_owner: None | str
    details: list[HealthOutDetailsType0Item] | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        status = self.status

        description: None | str
        description = self.description

        resolution_owner: None | str
        resolution_owner = self.resolution_owner

        details: list[dict[str, Any]] | None
        if isinstance(self.details, list):
            details = []
            for details_type_0_item_data in self.details:
                details_type_0_item = details_type_0_item_data.to_dict()
                details.append(details_type_0_item)

        else:
            details = self.details

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
                "status": status,
                "description": description,
                "resolution_owner": resolution_owner,
                "details": details,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.health_out_details_type_0_item import HealthOutDetailsType0Item  # noqa: PLC0415

        d = dict(src_dict)
        name = d.pop("name")

        status = d.pop("status")

        def _parse_description(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        description = _parse_description(d.pop("description"))

        def _parse_resolution_owner(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        resolution_owner = _parse_resolution_owner(d.pop("resolution_owner"))

        def _parse_details(data: object) -> list[HealthOutDetailsType0Item] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                details_type_0 = []
                _details_type_0 = data
                for details_type_0_item_data in _details_type_0:
                    details_type_0_item = HealthOutDetailsType0Item.from_dict(details_type_0_item_data)

                    details_type_0.append(details_type_0_item)

                return details_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[HealthOutDetailsType0Item] | None, data)

        details = _parse_details(d.pop("details"))

        health_out = cls(
            name=name,
            status=status,
            description=description,
            resolution_owner=resolution_owner,
            details=details,
        )

        health_out.additional_properties = d
        return health_out

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
