from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="SessionOut")


@_attrs_define
class SessionOut:
    """
    Attributes:
        id (UUID):
        organization_id (UUID):
        allowed_integration_ids (list[UUID]):
        connection_id (None | UUID):
        redirect_success (None | str):
        redirect_error (None | str):
        expires_at (datetime.datetime):
        used_at (datetime.datetime | None):
        created_at (datetime.datetime):
    """

    id: UUID
    organization_id: UUID
    allowed_integration_ids: list[UUID]
    connection_id: None | UUID
    redirect_success: None | str
    redirect_error: None | str
    expires_at: datetime.datetime
    used_at: datetime.datetime | None
    created_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        organization_id = str(self.organization_id)

        allowed_integration_ids = []
        for allowed_integration_ids_item_data in self.allowed_integration_ids:
            allowed_integration_ids_item = str(allowed_integration_ids_item_data)
            allowed_integration_ids.append(allowed_integration_ids_item)

        connection_id: None | str
        if isinstance(self.connection_id, UUID):
            connection_id = str(self.connection_id)
        else:
            connection_id = self.connection_id

        redirect_success: None | str
        redirect_success = self.redirect_success

        redirect_error: None | str
        redirect_error = self.redirect_error

        expires_at = self.expires_at.isoformat()

        used_at: None | str
        if isinstance(self.used_at, datetime.datetime):
            used_at = self.used_at.isoformat()
        else:
            used_at = self.used_at

        created_at = self.created_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "organization_id": organization_id,
                "allowed_integration_ids": allowed_integration_ids,
                "connection_id": connection_id,
                "redirect_success": redirect_success,
                "redirect_error": redirect_error,
                "expires_at": expires_at,
                "used_at": used_at,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = UUID(d.pop("id"))

        organization_id = UUID(d.pop("organization_id"))

        allowed_integration_ids = []
        _allowed_integration_ids = d.pop("allowed_integration_ids")
        for allowed_integration_ids_item_data in _allowed_integration_ids:
            allowed_integration_ids_item = UUID(allowed_integration_ids_item_data)

            allowed_integration_ids.append(allowed_integration_ids_item)

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

        def _parse_redirect_success(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        redirect_success = _parse_redirect_success(d.pop("redirect_success"))

        def _parse_redirect_error(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        redirect_error = _parse_redirect_error(d.pop("redirect_error"))

        expires_at = datetime.datetime.fromisoformat(d.pop("expires_at"))

        def _parse_used_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                used_at_type_0 = datetime.datetime.fromisoformat(data)

                return used_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        used_at = _parse_used_at(d.pop("used_at"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        session_out = cls(
            id=id,
            organization_id=organization_id,
            allowed_integration_ids=allowed_integration_ids,
            connection_id=connection_id,
            redirect_success=redirect_success,
            redirect_error=redirect_error,
            expires_at=expires_at,
            used_at=used_at,
            created_at=created_at,
        )

        session_out.additional_properties = d
        return session_out

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
