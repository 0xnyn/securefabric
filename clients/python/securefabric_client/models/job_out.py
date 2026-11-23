from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.job_out_options import JobOutOptions
    from ..models.stream_run_out import StreamRunOut


T = TypeVar("T", bound="JobOut")


@_attrs_define
class JobOut:
    """
    Attributes:
        id (UUID):
        connection_id (UUID):
        type_ (str):
        status (str):
        requested_by (None | str):
        options (JobOutOptions):
        health_code (None | str):
        failure_reason (None | str):
        created_at (datetime.datetime):
        started_at (datetime.datetime | None):
        finished_at (datetime.datetime | None):
        streams (list[StreamRunOut] | None):
    """

    id: UUID
    connection_id: UUID
    type_: str
    status: str
    requested_by: None | str
    options: JobOutOptions
    health_code: None | str
    failure_reason: None | str
    created_at: datetime.datetime
    started_at: datetime.datetime | None
    finished_at: datetime.datetime | None
    streams: list[StreamRunOut] | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        connection_id = str(self.connection_id)

        type_ = self.type_

        status = self.status

        requested_by: None | str
        requested_by = self.requested_by

        options = self.options.to_dict()

        health_code: None | str
        health_code = self.health_code

        failure_reason: None | str
        failure_reason = self.failure_reason

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

        streams: list[dict[str, Any]] | None
        if isinstance(self.streams, list):
            streams = []
            for streams_type_0_item_data in self.streams:
                streams_type_0_item = streams_type_0_item_data.to_dict()
                streams.append(streams_type_0_item)

        else:
            streams = self.streams

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "connection_id": connection_id,
                "type": type_,
                "status": status,
                "requested_by": requested_by,
                "options": options,
                "health_code": health_code,
                "failure_reason": failure_reason,
                "created_at": created_at,
                "started_at": started_at,
                "finished_at": finished_at,
                "streams": streams,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.job_out_options import JobOutOptions  # noqa: PLC0415
        from ..models.stream_run_out import StreamRunOut  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        connection_id = UUID(d.pop("connection_id"))

        type_ = d.pop("type")

        status = d.pop("status")

        def _parse_requested_by(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        requested_by = _parse_requested_by(d.pop("requested_by"))

        options = JobOutOptions.from_dict(d.pop("options"))

        def _parse_health_code(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        health_code = _parse_health_code(d.pop("health_code"))

        def _parse_failure_reason(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        failure_reason = _parse_failure_reason(d.pop("failure_reason"))

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

        def _parse_streams(data: object) -> list[StreamRunOut] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                streams_type_0 = []
                _streams_type_0 = data
                for streams_type_0_item_data in _streams_type_0:
                    streams_type_0_item = StreamRunOut.from_dict(streams_type_0_item_data)

                    streams_type_0.append(streams_type_0_item)

                return streams_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[StreamRunOut] | None, data)

        streams = _parse_streams(d.pop("streams"))

        job_out = cls(
            id=id,
            connection_id=connection_id,
            type_=type_,
            status=status,
            requested_by=requested_by,
            options=options,
            health_code=health_code,
            failure_reason=failure_reason,
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at,
            streams=streams,
        )

        job_out.additional_properties = d
        return job_out

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
