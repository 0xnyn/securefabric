from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="EndpointOut")


@_attrs_define
class EndpointOut:
    """
    Attributes:
        id (UUID):
        url (str):
        description (None | str):
        event_types (list[str]):
        enabled (bool):
        disabled_reason (None | str):
        failing_since (datetime.datetime | None):
        secret_hint (None | str):
        previous_secret_expires_at (datetime.datetime | None):
        created_at (datetime.datetime):
    """

    id: UUID
    url: str
    description: None | str
    event_types: list[str]
    enabled: bool
    disabled_reason: None | str
    failing_since: datetime.datetime | None
    secret_hint: None | str
    previous_secret_expires_at: datetime.datetime | None
    created_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        url = self.url

        description: None | str
        description = self.description

        event_types = self.event_types

        enabled = self.enabled

        disabled_reason: None | str
        disabled_reason = self.disabled_reason

        failing_since: None | str
        if isinstance(self.failing_since, datetime.datetime):
            failing_since = self.failing_since.isoformat()
        else:
            failing_since = self.failing_since

        secret_hint: None | str
        secret_hint = self.secret_hint

        previous_secret_expires_at: None | str
        if isinstance(self.previous_secret_expires_at, datetime.datetime):
            previous_secret_expires_at = self.previous_secret_expires_at.isoformat()
        else:
            previous_secret_expires_at = self.previous_secret_expires_at

        created_at = self.created_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "url": url,
                "description": description,
                "event_types": event_types,
                "enabled": enabled,
                "disabled_reason": disabled_reason,
                "failing_since": failing_since,
                "secret_hint": secret_hint,
                "previous_secret_expires_at": previous_secret_expires_at,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = UUID(d.pop("id"))

        url = d.pop("url")

        def _parse_description(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        description = _parse_description(d.pop("description"))

        event_types = cast(list[str], d.pop("event_types"))

        enabled = d.pop("enabled")

        def _parse_disabled_reason(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        disabled_reason = _parse_disabled_reason(d.pop("disabled_reason"))

        def _parse_failing_since(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                failing_since_type_0 = datetime.datetime.fromisoformat(data)

                return failing_since_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        failing_since = _parse_failing_since(d.pop("failing_since"))

        def _parse_secret_hint(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        secret_hint = _parse_secret_hint(d.pop("secret_hint"))

        def _parse_previous_secret_expires_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                previous_secret_expires_at_type_0 = datetime.datetime.fromisoformat(data)

                return previous_secret_expires_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        previous_secret_expires_at = _parse_previous_secret_expires_at(d.pop("previous_secret_expires_at"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        endpoint_out = cls(
            id=id,
            url=url,
            description=description,
            event_types=event_types,
            enabled=enabled,
            disabled_reason=disabled_reason,
            failing_since=failing_since,
            secret_hint=secret_hint,
            previous_secret_expires_at=previous_secret_expires_at,
            created_at=created_at,
        )

        endpoint_out.additional_properties = d
        return endpoint_out

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
