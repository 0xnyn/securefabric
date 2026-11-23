from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.vendor_attributes_data_type_0 import VendorAttributesDataType0
    from ..models.vendor_attributes_vulnerability_identifiers_item import VendorAttributesVulnerabilityIdentifiersItem


T = TypeVar("T", bound="VendorAttributes")


@_attrs_define
class VendorAttributes:
    """
    Attributes:
        id (str):
        url (None | str):
        severity (None | str):
        state (None | str):
        created_at (None | str):
        updated_at (None | str):
        vulnerability_identifiers (list[VendorAttributesVulnerabilityIdentifiersItem]):
        data (None | VendorAttributesDataType0):
    """

    id: str
    url: None | str
    severity: None | str
    state: None | str
    created_at: None | str
    updated_at: None | str
    vulnerability_identifiers: list[VendorAttributesVulnerabilityIdentifiersItem]
    data: None | VendorAttributesDataType0
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.vendor_attributes_data_type_0 import VendorAttributesDataType0  # noqa: PLC0415

        id = self.id

        url: None | str
        url = self.url

        severity: None | str
        severity = self.severity

        state: None | str
        state = self.state

        created_at: None | str
        created_at = self.created_at

        updated_at: None | str
        updated_at = self.updated_at

        vulnerability_identifiers = []
        for vulnerability_identifiers_item_data in self.vulnerability_identifiers:
            vulnerability_identifiers_item = vulnerability_identifiers_item_data.to_dict()
            vulnerability_identifiers.append(vulnerability_identifiers_item)

        data: dict[str, Any] | None
        if isinstance(self.data, VendorAttributesDataType0):
            data = self.data.to_dict()
        else:
            data = self.data

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "url": url,
                "severity": severity,
                "state": state,
                "created_at": created_at,
                "updated_at": updated_at,
                "vulnerability_identifiers": vulnerability_identifiers,
                "data": data,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.vendor_attributes_data_type_0 import VendorAttributesDataType0  # noqa: PLC0415
        from ..models.vendor_attributes_vulnerability_identifiers_item import (
            VendorAttributesVulnerabilityIdentifiersItem,  # noqa: PLC0415
        )

        d = dict(src_dict)
        id = d.pop("id")

        def _parse_url(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        url = _parse_url(d.pop("url"))

        def _parse_severity(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        severity = _parse_severity(d.pop("severity"))

        def _parse_state(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        state = _parse_state(d.pop("state"))

        def _parse_created_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        created_at = _parse_created_at(d.pop("created_at"))

        def _parse_updated_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        updated_at = _parse_updated_at(d.pop("updated_at"))

        vulnerability_identifiers = []
        _vulnerability_identifiers = d.pop("vulnerability_identifiers")
        for vulnerability_identifiers_item_data in _vulnerability_identifiers:
            vulnerability_identifiers_item = VendorAttributesVulnerabilityIdentifiersItem.from_dict(
                vulnerability_identifiers_item_data
            )

            vulnerability_identifiers.append(vulnerability_identifiers_item)

        def _parse_data(data: object) -> None | VendorAttributesDataType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                data_type_0 = VendorAttributesDataType0.from_dict(data)

                return data_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | VendorAttributesDataType0, data)

        data = _parse_data(d.pop("data"))

        vendor_attributes = cls(
            id=id,
            url=url,
            severity=severity,
            state=state,
            created_at=created_at,
            updated_at=updated_at,
            vulnerability_identifiers=vulnerability_identifiers,
            data=data,
        )

        vendor_attributes.additional_properties = d
        return vendor_attributes

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
