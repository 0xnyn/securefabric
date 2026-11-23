from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.audit_event_out_detail import AuditEventOutDetail


T = TypeVar("T", bound="AuditEventOut")


@_attrs_define
class AuditEventOut:
    """
    Attributes:
        id (UUID):
        actor_kind (str):
        actor_id (None | str):
        action (str):
        target_kind (None | str):
        target_id (None | str):
        ip (None | str):
        request_id (None | str):
        detail (AuditEventOutDetail):
        at (datetime.datetime):
    """

    id: UUID
    actor_kind: str
    actor_id: None | str
    action: str
    target_kind: None | str
    target_id: None | str
    ip: None | str
    request_id: None | str
    detail: AuditEventOutDetail
    at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        actor_kind = self.actor_kind

        actor_id: None | str
        actor_id = self.actor_id

        action = self.action

        target_kind: None | str
        target_kind = self.target_kind

        target_id: None | str
        target_id = self.target_id

        ip: None | str
        ip = self.ip

        request_id: None | str
        request_id = self.request_id

        detail = self.detail.to_dict()

        at = self.at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "actor_kind": actor_kind,
                "actor_id": actor_id,
                "action": action,
                "target_kind": target_kind,
                "target_id": target_id,
                "ip": ip,
                "request_id": request_id,
                "detail": detail,
                "at": at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.audit_event_out_detail import AuditEventOutDetail  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        actor_kind = d.pop("actor_kind")

        def _parse_actor_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        actor_id = _parse_actor_id(d.pop("actor_id"))

        action = d.pop("action")

        def _parse_target_kind(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        target_kind = _parse_target_kind(d.pop("target_kind"))

        def _parse_target_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        target_id = _parse_target_id(d.pop("target_id"))

        def _parse_ip(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        ip = _parse_ip(d.pop("ip"))

        def _parse_request_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        request_id = _parse_request_id(d.pop("request_id"))

        detail = AuditEventOutDetail.from_dict(d.pop("detail"))

        at = datetime.datetime.fromisoformat(d.pop("at"))

        audit_event_out = cls(
            id=id,
            actor_kind=actor_kind,
            actor_id=actor_id,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            ip=ip,
            request_id=request_id,
            detail=detail,
            at=at,
        )

        audit_event_out.additional_properties = d
        return audit_event_out

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
