from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="SessionCreated")


@_attrs_define
class SessionCreated:
    """
    Attributes:
        id (UUID):
        token (str): Bearer token for the connect UI. Shown once.
        url (str): Hosted connect page
        expires_at (datetime.datetime):
        organization_id (UUID):
        connection_id (None | UUID):
    """

    id: UUID
    token: str
    url: str
    expires_at: datetime.datetime
    organization_id: UUID
    connection_id: None | UUID
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        token = self.token

        url = self.url

        expires_at = self.expires_at.isoformat()

        organization_id = str(self.organization_id)

        connection_id: None | str
        if isinstance(self.connection_id, UUID):
            connection_id = str(self.connection_id)
        else:
            connection_id = self.connection_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "token": token,
                "url": url,
                "expires_at": expires_at,
                "organization_id": organization_id,
                "connection_id": connection_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = UUID(d.pop("id"))

        token = d.pop("token")

        url = d.pop("url")

        expires_at = datetime.datetime.fromisoformat(d.pop("expires_at"))

        organization_id = UUID(d.pop("organization_id"))

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

        session_created = cls(
            id=id,
            token=token,
            url=url,
            expires_at=expires_at,
            organization_id=organization_id,
            connection_id=connection_id,
        )

        session_created.additional_properties = d
        return session_created

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
