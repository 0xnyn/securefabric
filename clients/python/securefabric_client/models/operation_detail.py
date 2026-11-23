from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.operation_detail_summary import OperationDetailSummary
    from ..models.operation_line import OperationLine


T = TypeVar("T", bound="OperationDetail")


@_attrs_define
class OperationDetail:
    """
    Attributes:
        id (UUID):
        kind (str):
        action (str):
        status (str):
        vendor (None | str):
        connection_id (None | UUID):
        organization_id (None | UUID):
        job_id (None | UUID):
        stream_run_id (None | UUID):
        request_id (None | str):
        started_at (datetime.datetime):
        duration_ms (int | None):
        summary (OperationDetailSummary):
        line_count (int):  Default: 0.
        lines (list[OperationLine]):
    """

    id: UUID
    kind: str
    action: str
    status: str
    vendor: None | str
    connection_id: None | UUID
    organization_id: None | UUID
    job_id: None | UUID
    stream_run_id: None | UUID
    request_id: None | str
    started_at: datetime.datetime
    duration_ms: int | None
    summary: OperationDetailSummary
    lines: list[OperationLine]
    line_count: int = 0
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        kind = self.kind

        action = self.action

        status = self.status

        vendor: None | str
        vendor = self.vendor

        connection_id: None | str
        if isinstance(self.connection_id, UUID):
            connection_id = str(self.connection_id)
        else:
            connection_id = self.connection_id

        organization_id: None | str
        if isinstance(self.organization_id, UUID):
            organization_id = str(self.organization_id)
        else:
            organization_id = self.organization_id

        job_id: None | str
        if isinstance(self.job_id, UUID):
            job_id = str(self.job_id)
        else:
            job_id = self.job_id

        stream_run_id: None | str
        if isinstance(self.stream_run_id, UUID):
            stream_run_id = str(self.stream_run_id)
        else:
            stream_run_id = self.stream_run_id

        request_id: None | str
        request_id = self.request_id

        started_at = self.started_at.isoformat()

        duration_ms: int | None
        duration_ms = self.duration_ms

        summary = self.summary.to_dict()

        line_count = self.line_count

        lines = []
        for lines_item_data in self.lines:
            lines_item = lines_item_data.to_dict()
            lines.append(lines_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "kind": kind,
                "action": action,
                "status": status,
                "vendor": vendor,
                "connection_id": connection_id,
                "organization_id": organization_id,
                "job_id": job_id,
                "stream_run_id": stream_run_id,
                "request_id": request_id,
                "started_at": started_at,
                "duration_ms": duration_ms,
                "summary": summary,
                "line_count": line_count,
                "lines": lines,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.operation_detail_summary import OperationDetailSummary  # noqa: PLC0415
        from ..models.operation_line import OperationLine  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        kind = d.pop("kind")

        action = d.pop("action")

        status = d.pop("status")

        def _parse_vendor(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        vendor = _parse_vendor(d.pop("vendor"))

        def _parse_connection_id(data: object) -> None | UUID:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                connection_id_type_0 = UUID(data)

                return connection_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        connection_id = _parse_connection_id(d.pop("connection_id"))

        def _parse_organization_id(data: object) -> None | UUID:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                organization_id_type_0 = UUID(data)

                return organization_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        organization_id = _parse_organization_id(d.pop("organization_id"))

        def _parse_job_id(data: object) -> None | UUID:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                job_id_type_0 = UUID(data)

                return job_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        job_id = _parse_job_id(d.pop("job_id"))

        def _parse_stream_run_id(data: object) -> None | UUID:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                stream_run_id_type_0 = UUID(data)

                return stream_run_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        stream_run_id = _parse_stream_run_id(d.pop("stream_run_id"))

        def _parse_request_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        request_id = _parse_request_id(d.pop("request_id"))

        started_at = datetime.datetime.fromisoformat(d.pop("started_at"))

        def _parse_duration_ms(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        duration_ms = _parse_duration_ms(d.pop("duration_ms"))

        summary = OperationDetailSummary.from_dict(d.pop("summary"))

        line_count = d.pop("line_count")

        lines = []
        _lines = d.pop("lines")
        for lines_item_data in _lines:
            lines_item = OperationLine.from_dict(lines_item_data)

            lines.append(lines_item)

        operation_detail = cls(
            id=id,
            kind=kind,
            action=action,
            status=status,
            vendor=vendor,
            connection_id=connection_id,
            organization_id=organization_id,
            job_id=job_id,
            stream_run_id=stream_run_id,
            request_id=request_id,
            started_at=started_at,
            duration_ms=duration_ms,
            summary=summary,
            line_count=line_count,
            lines=lines,
        )

        operation_detail.additional_properties = d
        return operation_detail

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
