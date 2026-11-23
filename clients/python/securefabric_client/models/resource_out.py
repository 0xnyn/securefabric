from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.meta import Meta
    from ..models.resource_out_cloud_metadata_type_0 import ResourceOutCloudMetadataType0
    from ..models.resource_out_data_type_0 import ResourceOutDataType0
    from ..models.resource_out_groups_item import ResourceOutGroupsItem
    from ..models.resource_out_tags_item import ResourceOutTagsItem
    from ..models.resource_vendor_attributes import ResourceVendorAttributes


T = TypeVar("T", bound="ResourceOut")


@_attrs_define
class ResourceOut:
    """
    Attributes:
        id (str):
        name (str):
        type_ (str):
        state (str):
        vendor (str):
        url (None | str):
        groups (list[ResourceOutGroupsItem]):
        tags (list[ResourceOutTagsItem]):
        first_seen (None | str):
        last_seen (None | str):
        cloud_metadata (None | ResourceOutCloudMetadataType0):
        data (None | ResourceOutDataType0):
        vendor_attributes (ResourceVendorAttributes):
        connection_id (str):
        organization_id (str):
        is_stub (bool):  Default: False.
        created_at (None | str):
        updated_at (None | str):
        deleted_at (None | str):
        field_meta (Meta):
    """

    id: str
    name: str
    type_: str
    state: str
    vendor: str
    url: None | str
    groups: list[ResourceOutGroupsItem]
    tags: list[ResourceOutTagsItem]
    first_seen: None | str
    last_seen: None | str
    cloud_metadata: None | ResourceOutCloudMetadataType0
    data: None | ResourceOutDataType0
    vendor_attributes: ResourceVendorAttributes
    connection_id: str
    organization_id: str
    created_at: None | str
    updated_at: None | str
    deleted_at: None | str
    field_meta: Meta
    is_stub: bool = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.resource_out_cloud_metadata_type_0 import ResourceOutCloudMetadataType0  # noqa: PLC0415
        from ..models.resource_out_data_type_0 import ResourceOutDataType0  # noqa: PLC0415

        id = self.id

        name = self.name

        type_ = self.type_

        state = self.state

        vendor = self.vendor

        url: None | str
        url = self.url

        groups = []
        for groups_item_data in self.groups:
            groups_item = groups_item_data.to_dict()
            groups.append(groups_item)

        tags = []
        for tags_item_data in self.tags:
            tags_item = tags_item_data.to_dict()
            tags.append(tags_item)

        first_seen: None | str
        first_seen = self.first_seen

        last_seen: None | str
        last_seen = self.last_seen

        cloud_metadata: dict[str, Any] | None
        if isinstance(self.cloud_metadata, ResourceOutCloudMetadataType0):
            cloud_metadata = self.cloud_metadata.to_dict()
        else:
            cloud_metadata = self.cloud_metadata

        data: dict[str, Any] | None
        if isinstance(self.data, ResourceOutDataType0):
            data = self.data.to_dict()
        else:
            data = self.data

        vendor_attributes = self.vendor_attributes.to_dict()

        connection_id = self.connection_id

        organization_id = self.organization_id

        is_stub = self.is_stub

        created_at: None | str
        created_at = self.created_at

        updated_at: None | str
        updated_at = self.updated_at

        deleted_at: None | str
        deleted_at = self.deleted_at

        field_meta = self.field_meta.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "type": type_,
                "state": state,
                "vendor": vendor,
                "url": url,
                "groups": groups,
                "tags": tags,
                "first_seen": first_seen,
                "last_seen": last_seen,
                "cloud_metadata": cloud_metadata,
                "data": data,
                "vendor_attributes": vendor_attributes,
                "connection_id": connection_id,
                "organization_id": organization_id,
                "is_stub": is_stub,
                "created_at": created_at,
                "updated_at": updated_at,
                "deleted_at": deleted_at,
                "_meta": field_meta,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.meta import Meta  # noqa: PLC0415
        from ..models.resource_out_cloud_metadata_type_0 import ResourceOutCloudMetadataType0  # noqa: PLC0415
        from ..models.resource_out_data_type_0 import ResourceOutDataType0  # noqa: PLC0415
        from ..models.resource_out_groups_item import ResourceOutGroupsItem  # noqa: PLC0415
        from ..models.resource_out_tags_item import ResourceOutTagsItem  # noqa: PLC0415
        from ..models.resource_vendor_attributes import ResourceVendorAttributes  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        type_ = d.pop("type")

        state = d.pop("state")

        vendor = d.pop("vendor")

        def _parse_url(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        url = _parse_url(d.pop("url"))

        groups = []
        _groups = d.pop("groups")
        for groups_item_data in _groups:
            groups_item = ResourceOutGroupsItem.from_dict(groups_item_data)

            groups.append(groups_item)

        tags = []
        _tags = d.pop("tags")
        for tags_item_data in _tags:
            tags_item = ResourceOutTagsItem.from_dict(tags_item_data)

            tags.append(tags_item)

        def _parse_first_seen(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        first_seen = _parse_first_seen(d.pop("first_seen"))

        def _parse_last_seen(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        last_seen = _parse_last_seen(d.pop("last_seen"))

        def _parse_cloud_metadata(data: object) -> None | ResourceOutCloudMetadataType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                cloud_metadata_type_0 = ResourceOutCloudMetadataType0.from_dict(data)

                return cloud_metadata_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ResourceOutCloudMetadataType0, data)

        cloud_metadata = _parse_cloud_metadata(d.pop("cloud_metadata"))

        def _parse_data(data: object) -> None | ResourceOutDataType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                data_type_0 = ResourceOutDataType0.from_dict(data)

                return data_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ResourceOutDataType0, data)

        data = _parse_data(d.pop("data"))

        vendor_attributes = ResourceVendorAttributes.from_dict(d.pop("vendor_attributes"))

        connection_id = d.pop("connection_id")

        organization_id = d.pop("organization_id")

        is_stub = d.pop("is_stub")

        def _parse_created_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        created_at = _parse_created_at(d.pop("created_at"))

        def _parse_updated_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        updated_at = _parse_updated_at(d.pop("updated_at"))

        def _parse_deleted_at(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        deleted_at = _parse_deleted_at(d.pop("deleted_at"))

        field_meta = Meta.from_dict(d.pop("_meta"))

        resource_out = cls(
            id=id,
            name=name,
            type_=type_,
            state=state,
            vendor=vendor,
            url=url,
            groups=groups,
            tags=tags,
            first_seen=first_seen,
            last_seen=last_seen,
            cloud_metadata=cloud_metadata,
            data=data,
            vendor_attributes=vendor_attributes,
            connection_id=connection_id,
            organization_id=organization_id,
            is_stub=is_stub,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=deleted_at,
            field_meta=field_meta,
        )

        resource_out.additional_properties = d
        return resource_out

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
