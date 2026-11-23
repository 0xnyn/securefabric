from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.connector_out_actions_item import ConnectorOutActionsItem
    from ..models.connector_out_auth import ConnectorOutAuth
    from ..models.connector_out_capabilities import ConnectorOutCapabilities
    from ..models.connector_out_connection_config_schema import ConnectorOutConnectionConfigSchema
    from ..models.connector_out_credentials_schema import ConnectorOutCredentialsSchema
    from ..models.connector_out_options_schema import ConnectorOutOptionsSchema
    from ..models.connector_out_permissions_item import ConnectorOutPermissionsItem
    from ..models.connector_out_regions_item import ConnectorOutRegionsItem
    from ..models.connector_out_streams_item import ConnectorOutStreamsItem


T = TypeVar("T", bound="ConnectorOut")


@_attrs_define
class ConnectorOut:
    """
    Attributes:
        id (str):
        version (str):
        name (str):
        description (str):
        categories (list[str]):
        status (str):
        logo_url (None | str):
        docs_url (None | str):
        auth (ConnectorOutAuth):
        credentials_schema (ConnectorOutCredentialsSchema):
        connection_config_schema (ConnectorOutConnectionConfigSchema):
        options_schema (ConnectorOutOptionsSchema):
        regions (list[ConnectorOutRegionsItem]):
        permissions (list[ConnectorOutPermissionsItem]):
        streams (list[ConnectorOutStreamsItem]):
        actions (list[ConnectorOutActionsItem]):
        data_types (list[str]):
        capabilities (ConnectorOutCapabilities):
    """

    id: str
    version: str
    name: str
    description: str
    categories: list[str]
    status: str
    logo_url: None | str
    docs_url: None | str
    auth: ConnectorOutAuth
    credentials_schema: ConnectorOutCredentialsSchema
    connection_config_schema: ConnectorOutConnectionConfigSchema
    options_schema: ConnectorOutOptionsSchema
    regions: list[ConnectorOutRegionsItem]
    permissions: list[ConnectorOutPermissionsItem]
    streams: list[ConnectorOutStreamsItem]
    actions: list[ConnectorOutActionsItem]
    data_types: list[str]
    capabilities: ConnectorOutCapabilities
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        version = self.version

        name = self.name

        description = self.description

        categories = self.categories

        status = self.status

        logo_url: None | str
        logo_url = self.logo_url

        docs_url: None | str
        docs_url = self.docs_url

        auth = self.auth.to_dict()

        credentials_schema = self.credentials_schema.to_dict()

        connection_config_schema = self.connection_config_schema.to_dict()

        options_schema = self.options_schema.to_dict()

        regions = []
        for regions_item_data in self.regions:
            regions_item = regions_item_data.to_dict()
            regions.append(regions_item)

        permissions = []
        for permissions_item_data in self.permissions:
            permissions_item = permissions_item_data.to_dict()
            permissions.append(permissions_item)

        streams = []
        for streams_item_data in self.streams:
            streams_item = streams_item_data.to_dict()
            streams.append(streams_item)

        actions = []
        for actions_item_data in self.actions:
            actions_item = actions_item_data.to_dict()
            actions.append(actions_item)

        data_types = self.data_types

        capabilities = self.capabilities.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "version": version,
                "name": name,
                "description": description,
                "categories": categories,
                "status": status,
                "logo_url": logo_url,
                "docs_url": docs_url,
                "auth": auth,
                "credentials_schema": credentials_schema,
                "connection_config_schema": connection_config_schema,
                "options_schema": options_schema,
                "regions": regions,
                "permissions": permissions,
                "streams": streams,
                "actions": actions,
                "data_types": data_types,
                "capabilities": capabilities,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.connector_out_actions_item import ConnectorOutActionsItem  # noqa: PLC0415
        from ..models.connector_out_auth import ConnectorOutAuth  # noqa: PLC0415
        from ..models.connector_out_capabilities import ConnectorOutCapabilities  # noqa: PLC0415
        from ..models.connector_out_connection_config_schema import ConnectorOutConnectionConfigSchema  # noqa: PLC0415
        from ..models.connector_out_credentials_schema import ConnectorOutCredentialsSchema  # noqa: PLC0415
        from ..models.connector_out_options_schema import ConnectorOutOptionsSchema  # noqa: PLC0415
        from ..models.connector_out_permissions_item import ConnectorOutPermissionsItem  # noqa: PLC0415
        from ..models.connector_out_regions_item import ConnectorOutRegionsItem  # noqa: PLC0415
        from ..models.connector_out_streams_item import ConnectorOutStreamsItem  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id")

        version = d.pop("version")

        name = d.pop("name")

        description = d.pop("description")

        categories = cast(list[str], d.pop("categories"))

        status = d.pop("status")

        def _parse_logo_url(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        logo_url = _parse_logo_url(d.pop("logo_url"))

        def _parse_docs_url(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        docs_url = _parse_docs_url(d.pop("docs_url"))

        auth = ConnectorOutAuth.from_dict(d.pop("auth"))

        credentials_schema = ConnectorOutCredentialsSchema.from_dict(d.pop("credentials_schema"))

        connection_config_schema = ConnectorOutConnectionConfigSchema.from_dict(d.pop("connection_config_schema"))

        options_schema = ConnectorOutOptionsSchema.from_dict(d.pop("options_schema"))

        regions = []
        _regions = d.pop("regions")
        for regions_item_data in _regions:
            regions_item = ConnectorOutRegionsItem.from_dict(regions_item_data)

            regions.append(regions_item)

        permissions = []
        _permissions = d.pop("permissions")
        for permissions_item_data in _permissions:
            permissions_item = ConnectorOutPermissionsItem.from_dict(permissions_item_data)

            permissions.append(permissions_item)

        streams = []
        _streams = d.pop("streams")
        for streams_item_data in _streams:
            streams_item = ConnectorOutStreamsItem.from_dict(streams_item_data)

            streams.append(streams_item)

        actions = []
        _actions = d.pop("actions")
        for actions_item_data in _actions:
            actions_item = ConnectorOutActionsItem.from_dict(actions_item_data)

            actions.append(actions_item)

        data_types = cast(list[str], d.pop("data_types"))

        capabilities = ConnectorOutCapabilities.from_dict(d.pop("capabilities"))

        connector_out = cls(
            id=id,
            version=version,
            name=name,
            description=description,
            categories=categories,
            status=status,
            logo_url=logo_url,
            docs_url=docs_url,
            auth=auth,
            credentials_schema=credentials_schema,
            connection_config_schema=connection_config_schema,
            options_schema=options_schema,
            regions=regions,
            permissions=permissions,
            streams=streams,
            actions=actions,
            data_types=data_types,
            capabilities=capabilities,
        )

        connector_out.additional_properties = d
        return connector_out

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
