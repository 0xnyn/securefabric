from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="JobIn")


@_attrs_define
class JobIn:
    """
    Attributes:
        streams (list[str] | None | Unset):
        force_full_refresh (bool | Unset):  Default: False.
        since (datetime.datetime | None | Unset):
    """

    streams: list[str] | None | Unset = UNSET
    force_full_refresh: bool | Unset = False
    since: datetime.datetime | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        streams: list[str] | None | Unset
        if isinstance(self.streams, Unset):
            streams = UNSET
        elif isinstance(self.streams, list):
            streams = self.streams

        else:
            streams = self.streams

        force_full_refresh = self.force_full_refresh

        since: None | str | Unset
        if isinstance(self.since, Unset):
            since = UNSET
        elif isinstance(self.since, datetime.datetime):
            since = self.since.isoformat()
        else:
            since = self.since

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if streams is not UNSET:
            field_dict["streams"] = streams
        if force_full_refresh is not UNSET:
            field_dict["force_full_refresh"] = force_full_refresh
        if since is not UNSET:
            field_dict["since"] = since

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

        force_full_refresh = d.pop("force_full_refresh", UNSET)

        def _parse_since(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                since_type_0 = datetime.datetime.fromisoformat(data)

                return since_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        since = _parse_since(d.pop("since", UNSET))

        job_in = cls(
            streams=streams,
            force_full_refresh=force_full_refresh,
            since=since,
        )

        return job_in
