from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.environment_out_settings import EnvironmentOutSettings


T = TypeVar("T", bound="EnvironmentOut")


@_attrs_define
class EnvironmentOut:
    """
    Attributes:
        id (UUID):
        slug (str):
        name (str):
        is_production (bool):
        settings (EnvironmentOutSettings):
        created_at (datetime.datetime | None):
    """

    id: UUID
    slug: str
    name: str
    is_production: bool
    settings: EnvironmentOutSettings
    created_at: datetime.datetime | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        slug = self.slug

        name = self.name

        is_production = self.is_production

        settings = self.settings.to_dict()

        created_at: None | str
        if isinstance(self.created_at, datetime.datetime):
            created_at = self.created_at.isoformat()
        else:
            created_at = self.created_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "slug": slug,
                "name": name,
                "is_production": is_production,
                "settings": settings,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.environment_out_settings import EnvironmentOutSettings  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        slug = d.pop("slug")

        name = d.pop("name")

        is_production = d.pop("is_production")

        settings = EnvironmentOutSettings.from_dict(d.pop("settings"))

        def _parse_created_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                created_at_type_0 = datetime.datetime.fromisoformat(data)

                return created_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        created_at = _parse_created_at(d.pop("created_at"))

        environment_out = cls(
            id=id,
            slug=slug,
            name=name,
            is_production=is_production,
            settings=settings,
            created_at=created_at,
        )

        environment_out.additional_properties = d
        return environment_out

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
