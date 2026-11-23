from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.role_patch_role import RolePatchRole

T = TypeVar("T", bound="RolePatch")


@_attrs_define
class RolePatch:
    """
    Attributes:
        role (RolePatchRole):
    """

    role: RolePatchRole

    def to_dict(self) -> dict[str, Any]:
        role = self.role.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "role": role,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        role = RolePatchRole(d.pop("role"))

        role_patch = cls(
            role=role,
        )

        return role_patch
