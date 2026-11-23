from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="Authorization")


@_attrs_define
class Authorization:
    """
    Attributes:
        auth_mode (str):
        fields_set (list[str]):
        rotated_at (datetime.datetime | None):
        last_refresh_at (datetime.datetime | None):
        refresh_exhausted (bool):  Default: False.
    """

    auth_mode: str
    fields_set: list[str]
    rotated_at: datetime.datetime | None
    last_refresh_at: datetime.datetime | None
    refresh_exhausted: bool = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        auth_mode = self.auth_mode

        fields_set = self.fields_set

        rotated_at: None | str
        if isinstance(self.rotated_at, datetime.datetime):
            rotated_at = self.rotated_at.isoformat()
        else:
            rotated_at = self.rotated_at

        last_refresh_at: None | str
        if isinstance(self.last_refresh_at, datetime.datetime):
            last_refresh_at = self.last_refresh_at.isoformat()
        else:
            last_refresh_at = self.last_refresh_at

        refresh_exhausted = self.refresh_exhausted

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "auth_mode": auth_mode,
                "fields_set": fields_set,
                "rotated_at": rotated_at,
                "last_refresh_at": last_refresh_at,
                "refresh_exhausted": refresh_exhausted,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        auth_mode = d.pop("auth_mode")

        fields_set = cast(list[str], d.pop("fields_set"))

        def _parse_rotated_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                rotated_at_type_0 = datetime.datetime.fromisoformat(data)

                return rotated_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        rotated_at = _parse_rotated_at(d.pop("rotated_at"))

        def _parse_last_refresh_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                last_refresh_at_type_0 = datetime.datetime.fromisoformat(data)

                return last_refresh_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        last_refresh_at = _parse_last_refresh_at(d.pop("last_refresh_at"))

        refresh_exhausted = d.pop("refresh_exhausted")

        authorization = cls(
            auth_mode=auth_mode,
            fields_set=fields_set,
            rotated_at=rotated_at,
            last_refresh_at=last_refresh_at,
            refresh_exhausted=refresh_exhausted,
        )

        authorization.additional_properties = d
        return authorization

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
