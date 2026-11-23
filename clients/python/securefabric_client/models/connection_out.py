from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.connection_out_state import ConnectionOutState

if TYPE_CHECKING:
    from ..models.authorization import Authorization
    from ..models.connection_out_connection_config import ConnectionOutConnectionConfig
    from ..models.connection_out_metadata import ConnectionOutMetadata
    from ..models.connection_out_options import ConnectionOutOptions
    from ..models.connection_out_tags import ConnectionOutTags
    from ..models.health_out import HealthOut
    from ..models.stream_status import StreamStatus


T = TypeVar("T", bound="ConnectionOut")


@_attrs_define
class ConnectionOut:
    """
    Attributes:
        id (UUID):
        vendor (str):
        connector_version (str):
        identifier (None | str):
        organization_id (UUID):
        integration_id (UUID):
        state (ConnectionOutState):
        is_active (bool):
        is_sandbox (bool):
        direction (str):
        options (ConnectionOutOptions):
        connection_config (ConnectionOutConnectionConfig):
        metadata (ConnectionOutMetadata):
        tags (ConnectionOutTags):
        health (HealthOut):
        health_changed_at (datetime.datetime | None):
        pending_detail (None | str):
        created_at (datetime.datetime):
        updated_at (datetime.datetime):
        deleted_at (datetime.datetime | None):
        authorization (Authorization | None):
        streams (list[StreamStatus] | None):
        refresh_interval_secs (int | None):
        oauth2_authorize_url (None | str): Leen-compatible name for authorize_url
        authorize_url (None | str):
    """

    id: UUID
    vendor: str
    connector_version: str
    identifier: None | str
    organization_id: UUID
    integration_id: UUID
    state: ConnectionOutState
    is_active: bool
    is_sandbox: bool
    direction: str
    options: ConnectionOutOptions
    connection_config: ConnectionOutConnectionConfig
    metadata: ConnectionOutMetadata
    tags: ConnectionOutTags
    health: HealthOut
    health_changed_at: datetime.datetime | None
    pending_detail: None | str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    deleted_at: datetime.datetime | None
    authorization: Authorization | None
    streams: list[StreamStatus] | None
    refresh_interval_secs: int | None
    oauth2_authorize_url: None | str
    authorize_url: None | str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.authorization import Authorization  # noqa: PLC0415

        id = str(self.id)

        vendor = self.vendor

        connector_version = self.connector_version

        identifier: None | str
        identifier = self.identifier

        organization_id = str(self.organization_id)

        integration_id = str(self.integration_id)

        state = self.state.value

        is_active = self.is_active

        is_sandbox = self.is_sandbox

        direction = self.direction

        options = self.options.to_dict()

        connection_config = self.connection_config.to_dict()

        metadata = self.metadata.to_dict()

        tags = self.tags.to_dict()

        health = self.health.to_dict()

        health_changed_at: None | str
        if isinstance(self.health_changed_at, datetime.datetime):
            health_changed_at = self.health_changed_at.isoformat()
        else:
            health_changed_at = self.health_changed_at

        pending_detail: None | str
        pending_detail = self.pending_detail

        created_at = self.created_at.isoformat()

        updated_at = self.updated_at.isoformat()

        deleted_at: None | str
        if isinstance(self.deleted_at, datetime.datetime):
            deleted_at = self.deleted_at.isoformat()
        else:
            deleted_at = self.deleted_at

        authorization: dict[str, Any] | None
        if isinstance(self.authorization, Authorization):
            authorization = self.authorization.to_dict()
        else:
            authorization = self.authorization

        streams: list[dict[str, Any]] | None
        if isinstance(self.streams, list):
            streams = []
            for streams_type_0_item_data in self.streams:
                streams_type_0_item = streams_type_0_item_data.to_dict()
                streams.append(streams_type_0_item)

        else:
            streams = self.streams

        refresh_interval_secs: int | None
        refresh_interval_secs = self.refresh_interval_secs

        oauth2_authorize_url: None | str
        oauth2_authorize_url = self.oauth2_authorize_url

        authorize_url: None | str
        authorize_url = self.authorize_url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "vendor": vendor,
                "connector_version": connector_version,
                "identifier": identifier,
                "organization_id": organization_id,
                "integration_id": integration_id,
                "state": state,
                "is_active": is_active,
                "is_sandbox": is_sandbox,
                "direction": direction,
                "options": options,
                "connection_config": connection_config,
                "metadata": metadata,
                "tags": tags,
                "health": health,
                "health_changed_at": health_changed_at,
                "pending_detail": pending_detail,
                "created_at": created_at,
                "updated_at": updated_at,
                "deleted_at": deleted_at,
                "authorization": authorization,
                "streams": streams,
                "refresh_interval_secs": refresh_interval_secs,
                "oauth2_authorize_url": oauth2_authorize_url,
                "authorize_url": authorize_url,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.authorization import Authorization  # noqa: PLC0415
        from ..models.connection_out_connection_config import ConnectionOutConnectionConfig  # noqa: PLC0415
        from ..models.connection_out_metadata import ConnectionOutMetadata  # noqa: PLC0415
        from ..models.connection_out_options import ConnectionOutOptions  # noqa: PLC0415
        from ..models.connection_out_tags import ConnectionOutTags  # noqa: PLC0415
        from ..models.health_out import HealthOut  # noqa: PLC0415
        from ..models.stream_status import StreamStatus  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        vendor = d.pop("vendor")

        connector_version = d.pop("connector_version")

        def _parse_identifier(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        identifier = _parse_identifier(d.pop("identifier"))

        organization_id = UUID(d.pop("organization_id"))

        integration_id = UUID(d.pop("integration_id"))

        state = ConnectionOutState(d.pop("state"))

        is_active = d.pop("is_active")

        is_sandbox = d.pop("is_sandbox")

        direction = d.pop("direction")

        options = ConnectionOutOptions.from_dict(d.pop("options"))

        connection_config = ConnectionOutConnectionConfig.from_dict(d.pop("connection_config"))

        metadata = ConnectionOutMetadata.from_dict(d.pop("metadata"))

        tags = ConnectionOutTags.from_dict(d.pop("tags"))

        health = HealthOut.from_dict(d.pop("health"))

        def _parse_health_changed_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                health_changed_at_type_0 = datetime.datetime.fromisoformat(data)

                return health_changed_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        health_changed_at = _parse_health_changed_at(d.pop("health_changed_at"))

        def _parse_pending_detail(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        pending_detail = _parse_pending_detail(d.pop("pending_detail"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        updated_at = datetime.datetime.fromisoformat(d.pop("updated_at"))

        def _parse_deleted_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                deleted_at_type_0 = datetime.datetime.fromisoformat(data)

                return deleted_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        deleted_at = _parse_deleted_at(d.pop("deleted_at"))

        def _parse_authorization(data: object) -> Authorization | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                authorization_type_0 = Authorization.from_dict(data)

                return authorization_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(Authorization | None, data)

        authorization = _parse_authorization(d.pop("authorization"))

        def _parse_streams(data: object) -> list[StreamStatus] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                streams_type_0 = []
                _streams_type_0 = data
                for streams_type_0_item_data in _streams_type_0:
                    streams_type_0_item = StreamStatus.from_dict(streams_type_0_item_data)

                    streams_type_0.append(streams_type_0_item)

                return streams_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[StreamStatus] | None, data)

        streams = _parse_streams(d.pop("streams"))

        def _parse_refresh_interval_secs(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        refresh_interval_secs = _parse_refresh_interval_secs(d.pop("refresh_interval_secs"))

        def _parse_oauth2_authorize_url(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        oauth2_authorize_url = _parse_oauth2_authorize_url(d.pop("oauth2_authorize_url"))

        def _parse_authorize_url(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        authorize_url = _parse_authorize_url(d.pop("authorize_url"))

        connection_out = cls(
            id=id,
            vendor=vendor,
            connector_version=connector_version,
            identifier=identifier,
            organization_id=organization_id,
            integration_id=integration_id,
            state=state,
            is_active=is_active,
            is_sandbox=is_sandbox,
            direction=direction,
            options=options,
            connection_config=connection_config,
            metadata=metadata,
            tags=tags,
            health=health,
            health_changed_at=health_changed_at,
            pending_detail=pending_detail,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=deleted_at,
            authorization=authorization,
            streams=streams,
            refresh_interval_secs=refresh_interval_secs,
            oauth2_authorize_url=oauth2_authorize_url,
            authorize_url=authorize_url,
        )

        connection_out.additional_properties = d
        return connection_out

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
