from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.environment_patch_settings_type_0 import EnvironmentPatchSettingsType0


T = TypeVar("T", bound="EnvironmentPatch")


@_attrs_define
class EnvironmentPatch:
    """
    Attributes:
        name (None | str | Unset):
        settings (EnvironmentPatchSettingsType0 | None | Unset):
    """

    name: None | str | Unset = UNSET
    settings: EnvironmentPatchSettingsType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.environment_patch_settings_type_0 import EnvironmentPatchSettingsType0  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        settings: dict[str, Any] | None | Unset
        if isinstance(self.settings, Unset):
            settings = UNSET
        elif isinstance(self.settings, EnvironmentPatchSettingsType0):
            settings = self.settings.to_dict()
        else:
            settings = self.settings

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if settings is not UNSET:
            field_dict["settings"] = settings

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.environment_patch_settings_type_0 import EnvironmentPatchSettingsType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_settings(data: object) -> EnvironmentPatchSettingsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                settings_type_0 = EnvironmentPatchSettingsType0.from_dict(data)

                return settings_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(EnvironmentPatchSettingsType0 | None | Unset, data)

        settings = _parse_settings(d.pop("settings", UNSET))

        environment_patch = cls(
            name=name,
            settings=settings,
        )

        return environment_patch
