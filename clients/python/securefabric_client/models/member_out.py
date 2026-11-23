from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.member_out_role import MemberOutRole

T = TypeVar("T", bound="MemberOut")


@_attrs_define
class MemberOut:
    """
    Attributes:
        user_id (UUID):
        email (str):
        name (None | str):
        role (MemberOutRole):
        joined_at (datetime.datetime):
    """

    user_id: UUID
    email: str
    name: None | str
    role: MemberOutRole
    joined_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        user_id = str(self.user_id)

        email = self.email

        name: None | str
        name = self.name

        role = self.role.value

        joined_at = self.joined_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "user_id": user_id,
                "email": email,
                "name": name,
                "role": role,
                "joined_at": joined_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        user_id = UUID(d.pop("user_id"))

        email = d.pop("email")

        def _parse_name(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        name = _parse_name(d.pop("name"))

        role = MemberOutRole(d.pop("role"))

        joined_at = datetime.datetime.fromisoformat(d.pop("joined_at"))

        member_out = cls(
            user_id=user_id,
            email=email,
            name=name,
            role=role,
            joined_at=joined_at,
        )

        member_out.additional_properties = d
        return member_out

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
