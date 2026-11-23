from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.repair_in_params import RepairInParams


T = TypeVar("T", bound="RepairIn")


@_attrs_define
class RepairIn:
    """
    Attributes:
        params (RepairInParams | Unset):
    """

    params: RepairInParams | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        params: dict[str, Any] | Unset = UNSET
        if not isinstance(self.params, Unset):
            params = self.params.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if params is not UNSET:
            field_dict["params"] = params

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.repair_in_params import RepairInParams  # noqa: PLC0415

        d = dict(src_dict)
        _params = d.pop("params", UNSET)
        params: RepairInParams | Unset
        if isinstance(_params, Unset):
            params = UNSET
        else:
            params = RepairInParams.from_dict(_params)

        repair_in = cls(
            params=params,
        )

        return repair_in
