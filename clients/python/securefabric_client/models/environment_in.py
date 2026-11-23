from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="EnvironmentIn")


@_attrs_define
class EnvironmentIn:
    """
    Attributes:
        slug (str):
        name (str):
        is_production (bool | Unset):  Default: False.
    """

    slug: str
    name: str
    is_production: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        slug = self.slug

        name = self.name

        is_production = self.is_production

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "slug": slug,
                "name": name,
            }
        )
        if is_production is not UNSET:
            field_dict["is_production"] = is_production

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        slug = d.pop("slug")

        name = d.pop("name")

        is_production = d.pop("is_production", UNSET)

        environment_in = cls(
            slug=slug,
            name=name,
            is_production=is_production,
        )

        return environment_in
