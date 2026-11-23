from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="ResolveIn")


@_attrs_define
class ResolveIn:
    """
    Attributes:
        note (str): What was done (shown in history)
    """

    note: str

    def to_dict(self) -> dict[str, Any]:
        note = self.note

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "note": note,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        note = d.pop("note")

        resolve_in = cls(
            note=note,
        )

        return resolve_in
