from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.connect_session_view_branding import ConnectSessionViewBranding
    from ..models.connect_session_view_integrations_item import ConnectSessionViewIntegrationsItem
    from ..models.connect_session_view_option_presets import ConnectSessionViewOptionPresets
    from ..models.connect_session_view_organization_type_0 import ConnectSessionViewOrganizationType0


T = TypeVar("T", bound="ConnectSessionView")


@_attrs_define
class ConnectSessionView:
    """
    Attributes:
        id (UUID):
        organization (ConnectSessionViewOrganizationType0 | None):
        expires_at (datetime.datetime):
        used_at (datetime.datetime | None):
        reauthorize_connection_id (None | UUID):
        option_presets (ConnectSessionViewOptionPresets):
        integrations (list[ConnectSessionViewIntegrationsItem]):
        branding (ConnectSessionViewBranding):
        redirect_success (None | str):
        redirect_error (None | str):
    """

    id: UUID
    organization: ConnectSessionViewOrganizationType0 | None
    expires_at: datetime.datetime
    used_at: datetime.datetime | None
    reauthorize_connection_id: None | UUID
    option_presets: ConnectSessionViewOptionPresets
    integrations: list[ConnectSessionViewIntegrationsItem]
    branding: ConnectSessionViewBranding
    redirect_success: None | str
    redirect_error: None | str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.connect_session_view_organization_type_0 import ConnectSessionViewOrganizationType0  # noqa: PLC0415

        id = str(self.id)

        organization: dict[str, Any] | None
        if isinstance(self.organization, ConnectSessionViewOrganizationType0):
            organization = self.organization.to_dict()
        else:
            organization = self.organization

        expires_at = self.expires_at.isoformat()

        used_at: None | str
        if isinstance(self.used_at, datetime.datetime):
            used_at = self.used_at.isoformat()
        else:
            used_at = self.used_at

        reauthorize_connection_id: None | str
        if isinstance(self.reauthorize_connection_id, UUID):
            reauthorize_connection_id = str(self.reauthorize_connection_id)
        else:
            reauthorize_connection_id = self.reauthorize_connection_id

        option_presets = self.option_presets.to_dict()

        integrations = []
        for integrations_item_data in self.integrations:
            integrations_item = integrations_item_data.to_dict()
            integrations.append(integrations_item)

        branding = self.branding.to_dict()

        redirect_success: None | str
        redirect_success = self.redirect_success

        redirect_error: None | str
        redirect_error = self.redirect_error

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "organization": organization,
                "expires_at": expires_at,
                "used_at": used_at,
                "reauthorize_connection_id": reauthorize_connection_id,
                "option_presets": option_presets,
                "integrations": integrations,
                "branding": branding,
                "redirect_success": redirect_success,
                "redirect_error": redirect_error,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.connect_session_view_branding import ConnectSessionViewBranding  # noqa: PLC0415
        from ..models.connect_session_view_integrations_item import ConnectSessionViewIntegrationsItem  # noqa: PLC0415
        from ..models.connect_session_view_option_presets import ConnectSessionViewOptionPresets  # noqa: PLC0415
        from ..models.connect_session_view_organization_type_0 import ConnectSessionViewOrganizationType0  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        def _parse_organization(data: object) -> ConnectSessionViewOrganizationType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                organization_type_0 = ConnectSessionViewOrganizationType0.from_dict(data)

                return organization_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ConnectSessionViewOrganizationType0 | None, data)

        organization = _parse_organization(d.pop("organization"))

        expires_at = datetime.datetime.fromisoformat(d.pop("expires_at"))

        def _parse_used_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                used_at_type_0 = datetime.datetime.fromisoformat(data)

                return used_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        used_at = _parse_used_at(d.pop("used_at"))

        def _parse_reauthorize_connection_id(data: object) -> None | UUID:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                reauthorize_connection_id_type_0 = UUID(data)

                return reauthorize_connection_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        reauthorize_connection_id = _parse_reauthorize_connection_id(d.pop("reauthorize_connection_id"))

        option_presets = ConnectSessionViewOptionPresets.from_dict(d.pop("option_presets"))

        integrations = []
        _integrations = d.pop("integrations")
        for integrations_item_data in _integrations:
            integrations_item = ConnectSessionViewIntegrationsItem.from_dict(integrations_item_data)

            integrations.append(integrations_item)

        branding = ConnectSessionViewBranding.from_dict(d.pop("branding"))

        def _parse_redirect_success(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        redirect_success = _parse_redirect_success(d.pop("redirect_success"))

        def _parse_redirect_error(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        redirect_error = _parse_redirect_error(d.pop("redirect_error"))

        connect_session_view = cls(
            id=id,
            organization=organization,
            expires_at=expires_at,
            used_at=used_at,
            reauthorize_connection_id=reauthorize_connection_id,
            option_presets=option_presets,
            integrations=integrations,
            branding=branding,
            redirect_success=redirect_success,
            redirect_error=redirect_error,
        )

        connect_session_view.additional_properties = d
        return connect_session_view

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
