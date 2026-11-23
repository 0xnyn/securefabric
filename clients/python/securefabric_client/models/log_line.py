from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.log_line_http_type_0 import LogLineHttpType0


T = TypeVar("T", bound="LogLine")


@_attrs_define
class LogLine:
    """
    Attributes:
        at (datetime.datetime):
        level (str):
        kind (str):
        message (str):
        http (LogLineHttpType0 | None):
        operation_id (UUID):
        stream (None | str):
    """

    at: datetime.datetime
    level: str
    kind: str
    message: str
    http: LogLineHttpType0 | None
    operation_id: UUID
    stream: None | str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.log_line_http_type_0 import LogLineHttpType0  # noqa: PLC0415

        at = self.at.isoformat()

        level = self.level

        kind = self.kind

        message = self.message

        http: dict[str, Any] | None
        if isinstance(self.http, LogLineHttpType0):
            http = self.http.to_dict()
        else:
            http = self.http

        operation_id = str(self.operation_id)

        stream: None | str
        stream = self.stream

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "at": at,
                "level": level,
                "kind": kind,
                "message": message,
                "http": http,
                "operation_id": operation_id,
                "stream": stream,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.log_line_http_type_0 import LogLineHttpType0  # noqa: PLC0415

        d = dict(src_dict)
        at = datetime.datetime.fromisoformat(d.pop("at"))

        level = d.pop("level")

        kind = d.pop("kind")

        message = d.pop("message")

        def _parse_http(data: object) -> LogLineHttpType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                http_type_0 = LogLineHttpType0.from_dict(data)

                return http_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(LogLineHttpType0 | None, data)

        http = _parse_http(d.pop("http"))

        operation_id = UUID(d.pop("operation_id"))

        def _parse_stream(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        stream = _parse_stream(d.pop("stream"))

        log_line = cls(
            at=at,
            level=level,
            kind=kind,
            message=message,
            http=http,
            operation_id=operation_id,
            stream=stream,
        )

        log_line.additional_properties = d
        return log_line

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
