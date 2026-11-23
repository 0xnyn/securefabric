from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="ConnectOut")


@_attrs_define
class ConnectOut:
    """
    Attributes:
        id (UUID):
        state (str):
        authorize_url (None | str):
    """

    id: UUID
    state: str
    authorize_url: None | str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        state = self.state

        authorize_url: None | str
        authorize_url = self.authorize_url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "state": state,
                "authorize_url": authorize_url,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = UUID(d.pop("id"))

        state = d.pop("state")

        def _parse_authorize_url(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        authorize_url = _parse_authorize_url(d.pop("authorize_url"))

        connect_out = cls(
            id=id,
            state=state,
            authorize_url=authorize_url,
        )

        connect_out.additional_properties = d
        return connect_out

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
