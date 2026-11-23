from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.invite_in_role import InviteInRole
from ..types import UNSET, Unset

T = TypeVar("T", bound="InviteIn")


@_attrs_define
class InviteIn:
    """
    Attributes:
        email (str):
        role (InviteInRole | Unset):  Default: InviteInRole.DEVELOPER.
    """

    email: str
    role: InviteInRole | Unset = InviteInRole.DEVELOPER

    def to_dict(self) -> dict[str, Any]:
        email = self.email

        role: str | Unset = UNSET
        if not isinstance(self.role, Unset):
            role = self.role.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "email": email,
            }
        )
        if role is not UNSET:
            field_dict["role"] = role

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        email = d.pop("email")

        _role = d.pop("role", UNSET)
        role: InviteInRole | Unset
        if isinstance(_role, Unset):
            role = UNSET
        else:
            role = InviteInRole(_role)

        invite_in = cls(
            email=email,
            role=role,
        )

        return invite_in
