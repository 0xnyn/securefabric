from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.vendor_app_patch_config_type_0 import VendorAppPatchConfigType0
    from ..models.vendor_app_patch_secrets_type_0 import VendorAppPatchSecretsType0


T = TypeVar("T", bound="VendorAppPatch")


@_attrs_define
class VendorAppPatch:
    """
    Attributes:
        name (None | str | Unset):
        config (None | Unset | VendorAppPatchConfigType0):
        secrets (None | Unset | VendorAppPatchSecretsType0):
        webhook_secret (None | str | Unset):
    """

    name: None | str | Unset = UNSET
    config: None | Unset | VendorAppPatchConfigType0 = UNSET
    secrets: None | Unset | VendorAppPatchSecretsType0 = UNSET
    webhook_secret: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.vendor_app_patch_config_type_0 import VendorAppPatchConfigType0  # noqa: PLC0415
        from ..models.vendor_app_patch_secrets_type_0 import VendorAppPatchSecretsType0  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        config: dict[str, Any] | None | Unset
        if isinstance(self.config, Unset):
            config = UNSET
        elif isinstance(self.config, VendorAppPatchConfigType0):
            config = self.config.to_dict()
        else:
            config = self.config

        secrets: dict[str, Any] | None | Unset
        if isinstance(self.secrets, Unset):
            secrets = UNSET
        elif isinstance(self.secrets, VendorAppPatchSecretsType0):
            secrets = self.secrets.to_dict()
        else:
            secrets = self.secrets

        webhook_secret: None | str | Unset
        if isinstance(self.webhook_secret, Unset):
            webhook_secret = UNSET
        else:
            webhook_secret = self.webhook_secret

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if config is not UNSET:
            field_dict["config"] = config
        if secrets is not UNSET:
            field_dict["secrets"] = secrets
        if webhook_secret is not UNSET:
            field_dict["webhook_secret"] = webhook_secret

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.vendor_app_patch_config_type_0 import VendorAppPatchConfigType0  # noqa: PLC0415
        from ..models.vendor_app_patch_secrets_type_0 import VendorAppPatchSecretsType0  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_config(data: object) -> None | Unset | VendorAppPatchConfigType0:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                config_type_0 = VendorAppPatchConfigType0.from_dict(data)

                return config_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | VendorAppPatchConfigType0, data)

        config = _parse_config(d.pop("config", UNSET))

        def _parse_secrets(data: object) -> None | Unset | VendorAppPatchSecretsType0:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                secrets_type_0 = VendorAppPatchSecretsType0.from_dict(data)

                return secrets_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | VendorAppPatchSecretsType0, data)

        secrets = _parse_secrets(d.pop("secrets", UNSET))

        def _parse_webhook_secret(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        webhook_secret = _parse_webhook_secret(d.pop("webhook_secret", UNSET))

        vendor_app_patch = cls(
            name=name,
            config=config,
            secrets=secrets,
            webhook_secret=webhook_secret,
        )

        return vendor_app_patch
