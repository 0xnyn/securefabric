from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.resource_vendor_attributes_data_type_0 import ResourceVendorAttributesDataType0


T = TypeVar("T", bound="ResourceVendorAttributes")


@_attrs_define
class ResourceVendorAttributes:
    """
    Attributes:
        id (str):
        data (None | ResourceVendorAttributesDataType0):
    """

    id: str
    data: None | ResourceVendorAttributesDataType0
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.resource_vendor_attributes_data_type_0 import ResourceVendorAttributesDataType0  # noqa: PLC0415

        id = self.id

        data: dict[str, Any] | None
        if isinstance(self.data, ResourceVendorAttributesDataType0):
            data = self.data.to_dict()
        else:
            data = self.data

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "data": data,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.resource_vendor_attributes_data_type_0 import ResourceVendorAttributesDataType0  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id")

        def _parse_data(data: object) -> None | ResourceVendorAttributesDataType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                data_type_0 = ResourceVendorAttributesDataType0.from_dict(data)

                return data_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ResourceVendorAttributesDataType0, data)

        data = _parse_data(d.pop("data"))

        resource_vendor_attributes = cls(
            id=id,
            data=data,
        )

        resource_vendor_attributes.additional_properties = d
        return resource_vendor_attributes

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
