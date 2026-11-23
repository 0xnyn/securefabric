from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="EndpointIn")


@_attrs_define
class EndpointIn:
    """
    Attributes:
        url (str):
        description (None | str | Unset):
        event_types (list[str] | Unset): Empty means every event type
        enabled (bool | Unset):  Default: True.
    """

    url: str
    description: None | str | Unset = UNSET
    event_types: list[str] | Unset = UNSET
    enabled: bool | Unset = True

    def to_dict(self) -> dict[str, Any]:
        url = self.url

        description: None | str | Unset
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        event_types: list[str] | Unset = UNSET
        if not isinstance(self.event_types, Unset):
            event_types = self.event_types

        enabled = self.enabled

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "url": url,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if event_types is not UNSET:
            field_dict["event_types"] = event_types
        if enabled is not UNSET:
            field_dict["enabled"] = enabled

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        url = d.pop("url")

        def _parse_description(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))

        event_types = cast(list[str], d.pop("event_types", UNSET))

        enabled = d.pop("enabled", UNSET)

        endpoint_in = cls(
            url=url,
            description=description,
            event_types=event_types,
            enabled=enabled,
        )

        return endpoint_in
