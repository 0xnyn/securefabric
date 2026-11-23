from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.vendor_app_in_config import VendorAppInConfig
    from ..models.vendor_app_in_secrets import VendorAppInSecrets


T = TypeVar("T", bound="VendorAppIn")


@_attrs_define
class VendorAppIn:
    """
    Attributes:
        connector_id (str):
        name (str):
        base_url (str): https://github.com, https://<sub>.ghe.com or a GHES host
        config (VendorAppInConfig): Non-secret: app_id, slug, client_id, api_base_url, permission_tier
        secrets (VendorAppInSecrets): Write-only: private_key, client_secret
        webhook_secret (None | str | Unset):
    """

    connector_id: str
    name: str
    base_url: str
    config: VendorAppInConfig
    secrets: VendorAppInSecrets
    webhook_secret: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        connector_id = self.connector_id

        name = self.name

        base_url = self.base_url

        config = self.config.to_dict()

        secrets = self.secrets.to_dict()

        webhook_secret: None | str | Unset
        if isinstance(self.webhook_secret, Unset):
            webhook_secret = UNSET
        else:
            webhook_secret = self.webhook_secret

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "connector_id": connector_id,
                "name": name,
                "base_url": base_url,
                "config": config,
                "secrets": secrets,
            }
        )
        if webhook_secret is not UNSET:
            field_dict["webhook_secret"] = webhook_secret

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.vendor_app_in_config import VendorAppInConfig  # noqa: PLC0415
        from ..models.vendor_app_in_secrets import VendorAppInSecrets  # noqa: PLC0415

        d = dict(src_dict)
        connector_id = d.pop("connector_id")

        name = d.pop("name")

        base_url = d.pop("base_url")

        config = VendorAppInConfig.from_dict(d.pop("config"))

        secrets = VendorAppInSecrets.from_dict(d.pop("secrets"))

        def _parse_webhook_secret(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        webhook_secret = _parse_webhook_secret(d.pop("webhook_secret", UNSET))

        vendor_app_in = cls(
            connector_id=connector_id,
            name=name,
            base_url=base_url,
            config=config,
            secrets=secrets,
            webhook_secret=webhook_secret,
        )

        return vendor_app_in
