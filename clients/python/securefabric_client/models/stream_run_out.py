from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.stream_run_out_error_type_0 import StreamRunOutErrorType0


T = TypeVar("T", bound="StreamRunOut")


@_attrs_define
class StreamRunOut:
    """
    Attributes:
        id (UUID):
        stream (str):
        mode (str):
        state (str):
        priority (int):
        attempt (int):
        added (int):
        updated (int):
        deleted (int):
        unchanged (int):
        quarantined (int):
        pages (int):
        vendor_requests (int):
        health_code (None | str):
        warning (None | str):
        error (None | StreamRunOutErrorType0):
        not_before (datetime.datetime | None):
        created_at (datetime.datetime):
        started_at (datetime.datetime | None):
        finished_at (datetime.datetime | None):
    """

    id: UUID
    stream: str
    mode: str
    state: str
    priority: int
    attempt: int
    added: int
    updated: int
    deleted: int
    unchanged: int
    quarantined: int
    pages: int
    vendor_requests: int
    health_code: None | str
    warning: None | str
    error: None | StreamRunOutErrorType0
    not_before: datetime.datetime | None
    created_at: datetime.datetime
    started_at: datetime.datetime | None
    finished_at: datetime.datetime | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.stream_run_out_error_type_0 import StreamRunOutErrorType0  # noqa: PLC0415

        id = str(self.id)

        stream = self.stream

        mode = self.mode

        state = self.state

        priority = self.priority

        attempt = self.attempt

        added = self.added

        updated = self.updated

        deleted = self.deleted

        unchanged = self.unchanged

        quarantined = self.quarantined

        pages = self.pages

        vendor_requests = self.vendor_requests

        health_code: None | str
        health_code = self.health_code

        warning: None | str
        warning = self.warning

        error: dict[str, Any] | None
        if isinstance(self.error, StreamRunOutErrorType0):
            error = self.error.to_dict()
        else:
            error = self.error

        not_before: None | str
        if isinstance(self.not_before, datetime.datetime):
            not_before = self.not_before.isoformat()
        else:
            not_before = self.not_before

        created_at = self.created_at.isoformat()

        started_at: None | str
        if isinstance(self.started_at, datetime.datetime):
            started_at = self.started_at.isoformat()
        else:
            started_at = self.started_at

        finished_at: None | str
        if isinstance(self.finished_at, datetime.datetime):
            finished_at = self.finished_at.isoformat()
        else:
            finished_at = self.finished_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "stream": stream,
                "mode": mode,
                "state": state,
                "priority": priority,
                "attempt": attempt,
                "added": added,
                "updated": updated,
                "deleted": deleted,
                "unchanged": unchanged,
                "quarantined": quarantined,
                "pages": pages,
                "vendor_requests": vendor_requests,
                "health_code": health_code,
                "warning": warning,
                "error": error,
                "not_before": not_before,
                "created_at": created_at,
                "started_at": started_at,
                "finished_at": finished_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.stream_run_out_error_type_0 import StreamRunOutErrorType0  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        stream = d.pop("stream")

        mode = d.pop("mode")

        state = d.pop("state")

        priority = d.pop("priority")

        attempt = d.pop("attempt")

        added = d.pop("added")

        updated = d.pop("updated")

        deleted = d.pop("deleted")

        unchanged = d.pop("unchanged")

        quarantined = d.pop("quarantined")

        pages = d.pop("pages")

        vendor_requests = d.pop("vendor_requests")

        def _parse_health_code(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        health_code = _parse_health_code(d.pop("health_code"))

        def _parse_warning(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        warning = _parse_warning(d.pop("warning"))

        def _parse_error(data: object) -> None | StreamRunOutErrorType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                error_type_0 = StreamRunOutErrorType0.from_dict(data)

                return error_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | StreamRunOutErrorType0, data)

        error = _parse_error(d.pop("error"))

        def _parse_not_before(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                not_before_type_0 = datetime.datetime.fromisoformat(data)

                return not_before_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        not_before = _parse_not_before(d.pop("not_before"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        def _parse_started_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                started_at_type_0 = datetime.datetime.fromisoformat(data)

                return started_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        started_at = _parse_started_at(d.pop("started_at"))

        def _parse_finished_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                finished_at_type_0 = datetime.datetime.fromisoformat(data)

                return finished_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        finished_at = _parse_finished_at(d.pop("finished_at"))

        stream_run_out = cls(
            id=id,
            stream=stream,
            mode=mode,
            state=state,
            priority=priority,
            attempt=attempt,
            added=added,
            updated=updated,
            deleted=deleted,
            unchanged=unchanged,
            quarantined=quarantined,
            pages=pages,
            vendor_requests=vendor_requests,
            health_code=health_code,
            warning=warning,
            error=error,
            not_before=not_before,
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at,
        )

        stream_run_out.additional_properties = d
        return stream_run_out

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
