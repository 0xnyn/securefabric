from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.stream_status_capabilities import StreamStatusCapabilities


T = TypeVar("T", bound="StreamStatus")


@_attrs_define
class StreamStatus:
    """
    Attributes:
        name (str):
        object_ (str):
        enabled (bool):
        grant (None | str):
        grant_detail (None | str):
        endpoint (None | str):
        interval_s (int | None):
        schedule_state (None | str):
        next_run_at (datetime.datetime | None):
        last_success_at (datetime.datetime | None):
        record_count (int):  Default: 0.
        deleted_count (int):  Default: 0.
        capabilities (StreamStatusCapabilities):
    """

    name: str
    object_: str
    enabled: bool
    grant: None | str
    grant_detail: None | str
    endpoint: None | str
    interval_s: int | None
    schedule_state: None | str
    next_run_at: datetime.datetime | None
    last_success_at: datetime.datetime | None
    capabilities: StreamStatusCapabilities
    record_count: int = 0
    deleted_count: int = 0
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        object_ = self.object_

        enabled = self.enabled

        grant: None | str
        grant = self.grant

        grant_detail: None | str
        grant_detail = self.grant_detail

        endpoint: None | str
        endpoint = self.endpoint

        interval_s: int | None
        interval_s = self.interval_s

        schedule_state: None | str
        schedule_state = self.schedule_state

        next_run_at: None | str
        if isinstance(self.next_run_at, datetime.datetime):
            next_run_at = self.next_run_at.isoformat()
        else:
            next_run_at = self.next_run_at

        last_success_at: None | str
        if isinstance(self.last_success_at, datetime.datetime):
            last_success_at = self.last_success_at.isoformat()
        else:
            last_success_at = self.last_success_at

        record_count = self.record_count

        deleted_count = self.deleted_count

        capabilities = self.capabilities.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
                "object": object_,
                "enabled": enabled,
                "grant": grant,
                "grant_detail": grant_detail,
                "endpoint": endpoint,
                "interval_s": interval_s,
                "schedule_state": schedule_state,
                "next_run_at": next_run_at,
                "last_success_at": last_success_at,
                "record_count": record_count,
                "deleted_count": deleted_count,
                "capabilities": capabilities,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.stream_status_capabilities import StreamStatusCapabilities  # noqa: PLC0415

        d = dict(src_dict)
        name = d.pop("name")

        object_ = d.pop("object")

        enabled = d.pop("enabled")

        def _parse_grant(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        grant = _parse_grant(d.pop("grant"))

        def _parse_grant_detail(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        grant_detail = _parse_grant_detail(d.pop("grant_detail"))

        def _parse_endpoint(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        endpoint = _parse_endpoint(d.pop("endpoint"))

        def _parse_interval_s(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        interval_s = _parse_interval_s(d.pop("interval_s"))

        def _parse_schedule_state(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        schedule_state = _parse_schedule_state(d.pop("schedule_state"))

        def _parse_next_run_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                next_run_at_type_0 = datetime.datetime.fromisoformat(data)

                return next_run_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        next_run_at = _parse_next_run_at(d.pop("next_run_at"))

        def _parse_last_success_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                last_success_at_type_0 = datetime.datetime.fromisoformat(data)

                return last_success_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        last_success_at = _parse_last_success_at(d.pop("last_success_at"))

        record_count = d.pop("record_count")

        deleted_count = d.pop("deleted_count")

        capabilities = StreamStatusCapabilities.from_dict(d.pop("capabilities"))

        stream_status = cls(
            name=name,
            object_=object_,
            enabled=enabled,
            grant=grant,
            grant_detail=grant_detail,
            endpoint=endpoint,
            interval_s=interval_s,
            schedule_state=schedule_state,
            next_run_at=next_run_at,
            last_success_at=last_success_at,
            record_count=record_count,
            deleted_count=deleted_count,
            capabilities=capabilities,
        )

        stream_status.additional_properties = d
        return stream_status

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
