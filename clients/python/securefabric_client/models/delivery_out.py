from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.delivery_out_attempts_log_item import DeliveryOutAttemptsLogItem


T = TypeVar("T", bound="DeliveryOut")


@_attrs_define
class DeliveryOut:
    """
    Attributes:
        id (UUID):
        event_id (str):
        event_type (str):
        endpoint_id (UUID):
        status (str):
        attempts (int):
        next_attempt_at (datetime.datetime | None):
        last_status_code (int | None):
        last_latency_ms (int | None):
        last_error (None | str):
        created_at (datetime.datetime):
        delivered_at (datetime.datetime | None):
        attempts_log (list[DeliveryOutAttemptsLogItem]):
    """

    id: UUID
    event_id: str
    event_type: str
    endpoint_id: UUID
    status: str
    attempts: int
    next_attempt_at: datetime.datetime | None
    last_status_code: int | None
    last_latency_ms: int | None
    last_error: None | str
    created_at: datetime.datetime
    delivered_at: datetime.datetime | None
    attempts_log: list[DeliveryOutAttemptsLogItem]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        event_id = self.event_id

        event_type = self.event_type

        endpoint_id = str(self.endpoint_id)

        status = self.status

        attempts = self.attempts

        next_attempt_at: None | str
        if isinstance(self.next_attempt_at, datetime.datetime):
            next_attempt_at = self.next_attempt_at.isoformat()
        else:
            next_attempt_at = self.next_attempt_at

        last_status_code: int | None
        last_status_code = self.last_status_code

        last_latency_ms: int | None
        last_latency_ms = self.last_latency_ms

        last_error: None | str
        last_error = self.last_error

        created_at = self.created_at.isoformat()

        delivered_at: None | str
        if isinstance(self.delivered_at, datetime.datetime):
            delivered_at = self.delivered_at.isoformat()
        else:
            delivered_at = self.delivered_at

        attempts_log = []
        for attempts_log_item_data in self.attempts_log:
            attempts_log_item = attempts_log_item_data.to_dict()
            attempts_log.append(attempts_log_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "event_id": event_id,
                "event_type": event_type,
                "endpoint_id": endpoint_id,
                "status": status,
                "attempts": attempts,
                "next_attempt_at": next_attempt_at,
                "last_status_code": last_status_code,
                "last_latency_ms": last_latency_ms,
                "last_error": last_error,
                "created_at": created_at,
                "delivered_at": delivered_at,
                "attempts_log": attempts_log,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.delivery_out_attempts_log_item import DeliveryOutAttemptsLogItem  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        event_id = d.pop("event_id")

        event_type = d.pop("event_type")

        endpoint_id = UUID(d.pop("endpoint_id"))

        status = d.pop("status")

        attempts = d.pop("attempts")

        def _parse_next_attempt_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                next_attempt_at_type_0 = datetime.datetime.fromisoformat(data)

                return next_attempt_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        next_attempt_at = _parse_next_attempt_at(d.pop("next_attempt_at"))

        def _parse_last_status_code(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        last_status_code = _parse_last_status_code(d.pop("last_status_code"))

        def _parse_last_latency_ms(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        last_latency_ms = _parse_last_latency_ms(d.pop("last_latency_ms"))

        def _parse_last_error(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        last_error = _parse_last_error(d.pop("last_error"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        def _parse_delivered_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                delivered_at_type_0 = datetime.datetime.fromisoformat(data)

                return delivered_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        delivered_at = _parse_delivered_at(d.pop("delivered_at"))

        attempts_log = []
        _attempts_log = d.pop("attempts_log")
        for attempts_log_item_data in _attempts_log:
            attempts_log_item = DeliveryOutAttemptsLogItem.from_dict(attempts_log_item_data)

            attempts_log.append(attempts_log_item)

        delivery_out = cls(
            id=id,
            event_id=event_id,
            event_type=event_type,
            endpoint_id=endpoint_id,
            status=status,
            attempts=attempts,
            next_attempt_at=next_attempt_at,
            last_status_code=last_status_code,
            last_latency_ms=last_latency_ms,
            last_error=last_error,
            created_at=created_at,
            delivered_at=delivered_at,
            attempts_log=attempts_log,
        )

        delivery_out.additional_properties = d
        return delivery_out

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
