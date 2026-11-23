from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.organization_patch_metadata_type_0 import OrganizationPatchMetadataType0


T = TypeVar("T", bound="OrganizationPatch")


@_attrs_define
class OrganizationPatch:
    """
    Attributes:
        identifier (None | str | Unset):
        name (None | str | Unset):
        metadata (None | OrganizationPatchMetadataType0 | Unset):
    """

    identifier: None | str | Unset = UNSET
    name: None | str | Unset = UNSET
    metadata: None | OrganizationPatchMetadataType0 | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.organization_patch_metadata_type_0 import OrganizationPatchMetadataType0  # noqa: PLC0415

        identifier: None | str | Unset
        if isinstance(self.identifier, Unset):
            identifier = UNSET
        else:
            identifier = self.identifier

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        metadata: dict[str, Any] | None | Unset
        if isinstance(self.metadata, Unset):
            metadata = UNSET
        elif isinstance(self.metadata, OrganizationPatchMetadataType0):
            metadata = self.metadata.to_dict()
        else:
            metadata = self.metadata

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if identifier is not UNSET:
            field_dict["identifier"] = identifier
        if name is not UNSET:
            field_dict["name"] = name
        if metadata is not UNSET:
            field_dict["metadata"] = metadata

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.organization_patch_metadata_type_0 import OrganizationPatchMetadataType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_identifier(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        identifier = _parse_identifier(d.pop("identifier", UNSET))

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_metadata(data: object) -> None | OrganizationPatchMetadataType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                metadata_type_0 = OrganizationPatchMetadataType0.from_dict(data)

                return metadata_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | OrganizationPatchMetadataType0 | Unset, data)

        metadata = _parse_metadata(d.pop("metadata", UNSET))

        organization_patch = cls(
            identifier=identifier,
            name=name,
            metadata=metadata,
        )

        return organization_patch
