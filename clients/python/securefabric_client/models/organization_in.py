from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.organization_in_metadata_type_0 import OrganizationInMetadataType0


T = TypeVar("T", bound="OrganizationIn")


@_attrs_define
class OrganizationIn:
    """
    Attributes:
        identifier (str):
        name (str):
        metadata (None | OrganizationInMetadataType0 | Unset):
    """

    identifier: str
    name: str
    metadata: None | OrganizationInMetadataType0 | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.organization_in_metadata_type_0 import OrganizationInMetadataType0  # noqa: PLC0415

        identifier = self.identifier

        name = self.name

        metadata: dict[str, Any] | None | Unset
        if isinstance(self.metadata, Unset):
            metadata = UNSET
        elif isinstance(self.metadata, OrganizationInMetadataType0):
            metadata = self.metadata.to_dict()
        else:
            metadata = self.metadata

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "identifier": identifier,
                "name": name,
            }
        )
        if metadata is not UNSET:
            field_dict["metadata"] = metadata

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.organization_in_metadata_type_0 import OrganizationInMetadataType0  # noqa: PLC0415

        d = dict(src_dict)
        identifier = d.pop("identifier")

        name = d.pop("name")

        def _parse_metadata(data: object) -> None | OrganizationInMetadataType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                metadata_type_0 = OrganizationInMetadataType0.from_dict(data)

                return metadata_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | OrganizationInMetadataType0 | Unset, data)

        metadata = _parse_metadata(d.pop("metadata", UNSET))

        organization_in = cls(
            identifier=identifier,
            name=name,
            metadata=metadata,
        )

        return organization_in
