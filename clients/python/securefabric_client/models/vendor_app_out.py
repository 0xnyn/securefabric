from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.vendor_app_out_config import VendorAppOutConfig


T = TypeVar("T", bound="VendorAppOut")


@_attrs_define
class VendorAppOut:
    """
    Attributes:
        id (UUID):
        connector_id (str):
        name (str):
        base_url (str):
        config (VendorAppOutConfig):
        owner (str):
        is_default (bool):
        secrets_set (bool):
        webhook_secret_set (bool):
        created_at (datetime.datetime):
    """

    id: UUID
    connector_id: str
    name: str
    base_url: str
    config: VendorAppOutConfig
    owner: str
    is_default: bool
    secrets_set: bool
    webhook_secret_set: bool
    created_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        connector_id = self.connector_id

        name = self.name

        base_url = self.base_url

        config = self.config.to_dict()

        owner = self.owner

        is_default = self.is_default

        secrets_set = self.secrets_set

        webhook_secret_set = self.webhook_secret_set

        created_at = self.created_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "connector_id": connector_id,
                "name": name,
                "base_url": base_url,
                "config": config,
                "owner": owner,
                "is_default": is_default,
                "secrets_set": secrets_set,
                "webhook_secret_set": webhook_secret_set,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.vendor_app_out_config import VendorAppOutConfig  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        connector_id = d.pop("connector_id")

        name = d.pop("name")

        base_url = d.pop("base_url")

        config = VendorAppOutConfig.from_dict(d.pop("config"))

        owner = d.pop("owner")

        is_default = d.pop("is_default")

        secrets_set = d.pop("secrets_set")

        webhook_secret_set = d.pop("webhook_secret_set")

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        vendor_app_out = cls(
            id=id,
            connector_id=connector_id,
            name=name,
            base_url=base_url,
            config=config,
            owner=owner,
            is_default=is_default,
            secrets_set=secrets_set,
            webhook_secret_set=webhook_secret_set,
            created_at=created_at,
        )

        vendor_app_out.additional_properties = d
        return vendor_app_out

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
