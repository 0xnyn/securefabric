from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.connection_in_credentials_type_0 import ConnectionInCredentialsType0
    from ..models.connection_in_metadata_type_0 import ConnectionInMetadataType0
    from ..models.connection_in_options_type_0 import ConnectionInOptionsType0
    from ..models.connection_in_tags_type_0 import ConnectionInTagsType0


T = TypeVar("T", bound="ConnectionIn")


@_attrs_define
class ConnectionIn:
    """
    Attributes:
        vendor (None | str | Unset): e.g. GITHUB; resolves to the default integration
        integration (None | str | Unset): integration id or key
        credentials (ConnectionInCredentialsType0 | None | Unset): Write-only. Sealed before the request returns.
        options (ConnectionInOptionsType0 | None | Unset):
        identifier (None | str | Unset):
        metadata (ConnectionInMetadataType0 | None | Unset):
        tags (ConnectionInTagsType0 | None | Unset):
        is_sandbox (bool | Unset):  Default: False.
    """

    vendor: None | str | Unset = UNSET
    integration: None | str | Unset = UNSET
    credentials: ConnectionInCredentialsType0 | None | Unset = UNSET
    options: ConnectionInOptionsType0 | None | Unset = UNSET
    identifier: None | str | Unset = UNSET
    metadata: ConnectionInMetadataType0 | None | Unset = UNSET
    tags: ConnectionInTagsType0 | None | Unset = UNSET
    is_sandbox: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        from ..models.connection_in_credentials_type_0 import ConnectionInCredentialsType0  # noqa: PLC0415
        from ..models.connection_in_metadata_type_0 import ConnectionInMetadataType0  # noqa: PLC0415
        from ..models.connection_in_options_type_0 import ConnectionInOptionsType0  # noqa: PLC0415
        from ..models.connection_in_tags_type_0 import ConnectionInTagsType0  # noqa: PLC0415

        vendor: None | str | Unset
        if isinstance(self.vendor, Unset):
            vendor = UNSET
        else:
            vendor = self.vendor

        integration: None | str | Unset
        if isinstance(self.integration, Unset):
            integration = UNSET
        else:
            integration = self.integration

        credentials: dict[str, Any] | None | Unset
        if isinstance(self.credentials, Unset):
            credentials = UNSET
        elif isinstance(self.credentials, ConnectionInCredentialsType0):
            credentials = self.credentials.to_dict()
        else:
            credentials = self.credentials

        options: dict[str, Any] | None | Unset
        if isinstance(self.options, Unset):
            options = UNSET
        elif isinstance(self.options, ConnectionInOptionsType0):
            options = self.options.to_dict()
        else:
            options = self.options

        identifier: None | str | Unset
        if isinstance(self.identifier, Unset):
            identifier = UNSET
        else:
            identifier = self.identifier

        metadata: dict[str, Any] | None | Unset
        if isinstance(self.metadata, Unset):
            metadata = UNSET
        elif isinstance(self.metadata, ConnectionInMetadataType0):
            metadata = self.metadata.to_dict()
        else:
            metadata = self.metadata

        tags: dict[str, Any] | None | Unset
        if isinstance(self.tags, Unset):
            tags = UNSET
        elif isinstance(self.tags, ConnectionInTagsType0):
            tags = self.tags.to_dict()
        else:
            tags = self.tags

        is_sandbox = self.is_sandbox

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if vendor is not UNSET:
            field_dict["vendor"] = vendor
        if integration is not UNSET:
            field_dict["integration"] = integration
        if credentials is not UNSET:
            field_dict["credentials"] = credentials
        if options is not UNSET:
            field_dict["options"] = options
        if identifier is not UNSET:
            field_dict["identifier"] = identifier
        if metadata is not UNSET:
            field_dict["metadata"] = metadata
        if tags is not UNSET:
            field_dict["tags"] = tags
        if is_sandbox is not UNSET:
            field_dict["is_sandbox"] = is_sandbox

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.connection_in_credentials_type_0 import ConnectionInCredentialsType0  # noqa: PLC0415
        from ..models.connection_in_metadata_type_0 import ConnectionInMetadataType0  # noqa: PLC0415
        from ..models.connection_in_options_type_0 import ConnectionInOptionsType0  # noqa: PLC0415
        from ..models.connection_in_tags_type_0 import ConnectionInTagsType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_vendor(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        vendor = _parse_vendor(d.pop("vendor", UNSET))

        def _parse_integration(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        integration = _parse_integration(d.pop("integration", UNSET))

        def _parse_credentials(data: object) -> ConnectionInCredentialsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                credentials_type_0 = ConnectionInCredentialsType0.from_dict(data)

                return credentials_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ConnectionInCredentialsType0 | None | Unset, data)

        credentials = _parse_credentials(d.pop("credentials", UNSET))

        def _parse_options(data: object) -> ConnectionInOptionsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                options_type_0 = ConnectionInOptionsType0.from_dict(data)

                return options_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ConnectionInOptionsType0 | None | Unset, data)

        options = _parse_options(d.pop("options", UNSET))

        def _parse_identifier(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        identifier = _parse_identifier(d.pop("identifier", UNSET))

        def _parse_metadata(data: object) -> ConnectionInMetadataType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                metadata_type_0 = ConnectionInMetadataType0.from_dict(data)

                return metadata_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ConnectionInMetadataType0 | None | Unset, data)

        metadata = _parse_metadata(d.pop("metadata", UNSET))

        def _parse_tags(data: object) -> ConnectionInTagsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                tags_type_0 = ConnectionInTagsType0.from_dict(data)

                return tags_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ConnectionInTagsType0 | None | Unset, data)

        tags = _parse_tags(d.pop("tags", UNSET))

        is_sandbox = d.pop("is_sandbox", UNSET)

        connection_in = cls(
            vendor=vendor,
            integration=integration,
            credentials=credentials,
            options=options,
            identifier=identifier,
            metadata=metadata,
            tags=tags,
            is_sandbox=is_sandbox,
        )

        return connection_in
