from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.session_in_option_presets_type_0 import SessionInOptionPresetsType0


T = TypeVar("T", bound="SessionIn")


@_attrs_define
class SessionIn:
    """
    Attributes:
        organization_id (UUID):
        integrations (list[str] | None | Unset): Integration ids, keys or vendor names
        connection_id (None | Unset | UUID): Re-authorise this connection (CON-09)
        option_presets (None | SessionInOptionPresetsType0 | Unset):
        redirect_success (None | str | Unset):
        redirect_error (None | str | Unset):
    """

    organization_id: UUID
    integrations: list[str] | None | Unset = UNSET
    connection_id: None | Unset | UUID = UNSET
    option_presets: None | SessionInOptionPresetsType0 | Unset = UNSET
    redirect_success: None | str | Unset = UNSET
    redirect_error: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.session_in_option_presets_type_0 import SessionInOptionPresetsType0  # noqa: PLC0415

        organization_id = str(self.organization_id)

        integrations: list[str] | None | Unset
        if isinstance(self.integrations, Unset):
            integrations = UNSET
        elif isinstance(self.integrations, list):
            integrations = self.integrations

        else:
            integrations = self.integrations

        connection_id: None | str | Unset
        if isinstance(self.connection_id, Unset):
            connection_id = UNSET
        elif isinstance(self.connection_id, UUID):
            connection_id = str(self.connection_id)
        else:
            connection_id = self.connection_id

        option_presets: dict[str, Any] | None | Unset
        if isinstance(self.option_presets, Unset):
            option_presets = UNSET
        elif isinstance(self.option_presets, SessionInOptionPresetsType0):
            option_presets = self.option_presets.to_dict()
        else:
            option_presets = self.option_presets

        redirect_success: None | str | Unset
        if isinstance(self.redirect_success, Unset):
            redirect_success = UNSET
        else:
            redirect_success = self.redirect_success

        redirect_error: None | str | Unset
        if isinstance(self.redirect_error, Unset):
            redirect_error = UNSET
        else:
            redirect_error = self.redirect_error

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "organization_id": organization_id,
            }
        )
        if integrations is not UNSET:
            field_dict["integrations"] = integrations
        if connection_id is not UNSET:
            field_dict["connection_id"] = connection_id
        if option_presets is not UNSET:
            field_dict["option_presets"] = option_presets
        if redirect_success is not UNSET:
            field_dict["redirect_success"] = redirect_success
        if redirect_error is not UNSET:
            field_dict["redirect_error"] = redirect_error

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.session_in_option_presets_type_0 import SessionInOptionPresetsType0  # noqa: PLC0415

        d = dict(src_dict)
        organization_id = UUID(d.pop("organization_id"))

        def _parse_integrations(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                integrations_type_0 = cast(list[str], data)

                return integrations_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        integrations = _parse_integrations(d.pop("integrations", UNSET))

        def _parse_connection_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                connection_id_type_0 = UUID(data)

                return connection_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        connection_id = _parse_connection_id(d.pop("connection_id", UNSET))

        def _parse_option_presets(data: object) -> None | SessionInOptionPresetsType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                option_presets_type_0 = SessionInOptionPresetsType0.from_dict(data)

                return option_presets_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | SessionInOptionPresetsType0 | Unset, data)

        option_presets = _parse_option_presets(d.pop("option_presets", UNSET))

        def _parse_redirect_success(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        redirect_success = _parse_redirect_success(d.pop("redirect_success", UNSET))

        def _parse_redirect_error(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        redirect_error = _parse_redirect_error(d.pop("redirect_error", UNSET))

        session_in = cls(
            organization_id=organization_id,
            integrations=integrations,
            connection_id=connection_id,
            option_presets=option_presets,
            redirect_success=redirect_success,
            redirect_error=redirect_error,
        )

        return session_in
