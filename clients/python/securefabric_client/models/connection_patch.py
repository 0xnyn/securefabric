from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.connection_patch_state_type_0 import ConnectionPatchStateType0
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.connection_patch_credentials_type_0 import ConnectionPatchCredentialsType0
    from ..models.connection_patch_options_type_0 import ConnectionPatchOptionsType0
    from ..models.connection_patch_tags_type_0 import ConnectionPatchTagsType0


T = TypeVar("T", bound="ConnectionPatch")


@_attrs_define
class ConnectionPatch:
    """
    Attributes:
        state (ConnectionPatchStateType0 | None | Unset):
        options (ConnectionPatchOptionsType0 | None | Unset):
        credentials (ConnectionPatchCredentialsType0 | None | Unset): Rotation: verified before swapping (AUTH-11)
        tags (ConnectionPatchTagsType0 | None | Unset):
        identifier (None | str | Unset):
    """

    state: ConnectionPatchStateType0 | None | Unset = UNSET
    options: ConnectionPatchOptionsType0 | None | Unset = UNSET
    credentials: ConnectionPatchCredentialsType0 | None | Unset = UNSET
    tags: ConnectionPatchTagsType0 | None | Unset = UNSET
    identifier: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.connection_patch_credentials_type_0 import ConnectionPatchCredentialsType0  # noqa: PLC0415
        from ..models.connection_patch_options_type_0 import ConnectionPatchOptionsType0  # noqa: PLC0415
        from ..models.connection_patch_tags_type_0 import ConnectionPatchTagsType0  # noqa: PLC0415

        state: None | str | Unset
        if isinstance(self.state, Unset):
            state = UNSET
        elif isinstance(self.state, ConnectionPatchStateType0):
            state = self.state.value
        else:
            state = self.state

        options: dict[str, Any] | None | Unset
        if isinstance(self.options, Unset):
            options = UNSET
        elif isinstance(self.options, ConnectionPatchOptionsType0):
            options = self.options.to_dict()
        else:
            options = self.options

        credentials: dict[str, Any] | None | Unset
        if isinstance(self.credentials, Unset):
            credentials = UNSET
        elif isinstance(self.credentials, ConnectionPatchCredentialsType0):
            credentials = self.credentials.to_dict()
        else:
            credentials = self.credentials

        tags: dict[str, Any] | None | Unset
        if isinstance(self.tags, Unset):
            tags = UNSET
        elif isinstance(self.tags, ConnectionPatchTagsType0):
            tags = self.tags.to_dict()
        else:
            tags = self.tags

        identifier: None | str | Unset
        if isinstance(self.identifier, Unset):
            identifier = UNSET
        else:
            identifier = self.identifier

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if state is not UNSET:
            field_dict["state"] = state
        if options is not UNSET:
            field_dict["options"] = options
        if credentials is not UNSET:
            field_dict["credentials"] = credentials
        if tags is not UNSET:
            field_dict["tags"] = tags
        if identifier is not UNSET:
            field_dict["identifier"] = identifier

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.connection_patch_credentials_type_0 import ConnectionPatchCredentialsType0  # noqa: PLC0415
        from ..models.connection_patch_options_type_0 import ConnectionPatchOptionsType0  # noqa: PLC0415
        from ..models.connection_patch_tags_type_0 import ConnectionPatchTagsType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_state(data: object) -> ConnectionPatchStateType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                state_type_0 = ConnectionPatchStateType0(data)

                return state_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ConnectionPatchStateType0 | None | Unset, data)

        state = _parse_state(d.pop("state", UNSET))

        def _parse_options(data: object) -> ConnectionPatchOptionsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                options_type_0 = ConnectionPatchOptionsType0.from_dict(data)

                return options_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ConnectionPatchOptionsType0 | None | Unset, data)

        options = _parse_options(d.pop("options", UNSET))

        def _parse_credentials(data: object) -> ConnectionPatchCredentialsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                credentials_type_0 = ConnectionPatchCredentialsType0.from_dict(data)

                return credentials_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ConnectionPatchCredentialsType0 | None | Unset, data)

        credentials = _parse_credentials(d.pop("credentials", UNSET))

        def _parse_tags(data: object) -> ConnectionPatchTagsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                tags_type_0 = ConnectionPatchTagsType0.from_dict(data)

                return tags_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ConnectionPatchTagsType0 | None | Unset, data)

        tags = _parse_tags(d.pop("tags", UNSET))

        def _parse_identifier(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        identifier = _parse_identifier(d.pop("identifier", UNSET))

        connection_patch = cls(
            state=state,
            options=options,
            credentials=credentials,
            tags=tags,
            identifier=identifier,
        )

        return connection_patch
