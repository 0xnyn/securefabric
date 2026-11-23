from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="ResetIn")


@_attrs_define
class ResetIn:
    """
    Attributes:
        streams (list[str] | None | Unset):
        wipe (bool | Unset): Delete the connection's rows first (admins only) Default: False.
    """

    streams: list[str] | None | Unset = UNSET
    wipe: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        streams: list[str] | None | Unset
        if isinstance(self.streams, Unset):
            streams = UNSET
        elif isinstance(self.streams, list):
            streams = self.streams

        else:
            streams = self.streams

        wipe = self.wipe

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if streams is not UNSET:
            field_dict["streams"] = streams
        if wipe is not UNSET:
            field_dict["wipe"] = wipe

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_streams(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                streams_type_0 = cast(list[str], data)

                return streams_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        streams = _parse_streams(d.pop("streams", UNSET))

        wipe = d.pop("wipe", UNSET)

        reset_in = cls(
            streams=streams,
            wipe=wipe,
        )

        return reset_in
