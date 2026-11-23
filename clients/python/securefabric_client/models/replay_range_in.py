from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="ReplayRangeIn")


@_attrs_define
class ReplayRangeIn:
    """
    Attributes:
        since (datetime.datetime):
        until (datetime.datetime | None | Unset):
    """

    since: datetime.datetime
    until: datetime.datetime | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        since = self.since.isoformat()

        until: None | str | Unset
        if isinstance(self.until, Unset):
            until = UNSET
        elif isinstance(self.until, datetime.datetime):
            until = self.until.isoformat()
        else:
            until = self.until

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "since": since,
            }
        )
        if until is not UNSET:
            field_dict["until"] = until

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        since = datetime.datetime.fromisoformat(d.pop("since"))

        def _parse_until(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                until_type_0 = datetime.datetime.fromisoformat(data)

                return until_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        until = _parse_until(d.pop("until", UNSET))

        replay_range_in = cls(
            since=since,
            until=until,
        )

        return replay_range_in
