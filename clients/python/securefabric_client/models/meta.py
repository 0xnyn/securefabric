from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Meta")


@_attrs_define
class Meta:
    """
    Attributes:
        derived (list[str]):
        stream (str):
        connector_version (None | str):
        natural_key (str):
    """

    derived: list[str]
    stream: str
    connector_version: None | str
    natural_key: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        derived = self.derived

        stream = self.stream

        connector_version: None | str
        connector_version = self.connector_version

        natural_key = self.natural_key

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "derived": derived,
                "stream": stream,
                "connector_version": connector_version,
                "natural_key": natural_key,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        derived = cast(list[str], d.pop("derived"))

        stream = d.pop("stream")

        def _parse_connector_version(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        connector_version = _parse_connector_version(d.pop("connector_version"))

        natural_key = d.pop("natural_key")

        meta = cls(
            derived=derived,
            stream=stream,
            connector_version=connector_version,
            natural_key=natural_key,
        )

        meta.additional_properties = d
        return meta

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
