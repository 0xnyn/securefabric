from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="OnboardIn")


@_attrs_define
class OnboardIn:
    """
    Attributes:
        account_name (str):
    """

    account_name: str

    def to_dict(self) -> dict[str, Any]:
        account_name = self.account_name

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "account_name": account_name,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        account_name = d.pop("account_name")

        onboard_in = cls(
            account_name=account_name,
        )

        return onboard_in
