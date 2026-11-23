from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.organization_out_metadata import OrganizationOutMetadata


T = TypeVar("T", bound="OrganizationOut")


@_attrs_define
class OrganizationOut:
    """
    Attributes:
        id (UUID):
        identifier (str):
        name (str):
        metadata (OrganizationOutMetadata):
        connection_count (int):  Default: 0.
        created_at (datetime.datetime):
        updated_at (datetime.datetime):
    """

    id: UUID
    identifier: str
    name: str
    metadata: OrganizationOutMetadata
    created_at: datetime.datetime
    updated_at: datetime.datetime
    connection_count: int = 0
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        identifier = self.identifier

        name = self.name

        metadata = self.metadata.to_dict()

        connection_count = self.connection_count

        created_at = self.created_at.isoformat()

        updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "identifier": identifier,
                "name": name,
                "metadata": metadata,
                "connection_count": connection_count,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.organization_out_metadata import OrganizationOutMetadata  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        identifier = d.pop("identifier")

        name = d.pop("name")

        metadata = OrganizationOutMetadata.from_dict(d.pop("metadata"))

        connection_count = d.pop("connection_count")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        organization_out = cls(
            id=id,
            identifier=identifier,
            name=name,
            metadata=metadata,
            connection_count=connection_count,
            created_at=created_at,
            updated_at=updated_at,
        )

        organization_out.additional_properties = d
        return organization_out

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
