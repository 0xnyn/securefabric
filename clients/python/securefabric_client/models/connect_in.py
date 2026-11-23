from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.connect_in_credentials_type_0 import ConnectInCredentialsType0
    from ..models.connect_in_options_type_0 import ConnectInOptionsType0


T = TypeVar("T", bound="ConnectIn")


@_attrs_define
class ConnectIn:
    """
    Attributes:
        integration (str):
        credentials (ConnectInCredentialsType0 | None | Unset):
        options (ConnectInOptionsType0 | None | Unset):
        mode (str | Unset): install | authorize (the app is already installed) Default: 'install'.
    """

    integration: str
    credentials: ConnectInCredentialsType0 | None | Unset = UNSET
    options: ConnectInOptionsType0 | None | Unset = UNSET
    mode: str | Unset = "install"

    def to_dict(self) -> dict[str, Any]:
        from ..models.connect_in_credentials_type_0 import ConnectInCredentialsType0  # noqa: PLC0415
        from ..models.connect_in_options_type_0 import ConnectInOptionsType0  # noqa: PLC0415

        integration = self.integration

        credentials: dict[str, Any] | None | Unset
        if isinstance(self.credentials, Unset):
            credentials = UNSET
        elif isinstance(self.credentials, ConnectInCredentialsType0):
            credentials = self.credentials.to_dict()
        else:
            credentials = self.credentials

        options: dict[str, Any] | None | Unset
        if isinstance(self.options, Unset):
            options = UNSET
        elif isinstance(self.options, ConnectInOptionsType0):
            options = self.options.to_dict()
        else:
            options = self.options

        mode = self.mode

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "integration": integration,
            }
        )
        if credentials is not UNSET:
            field_dict["credentials"] = credentials
        if options is not UNSET:
            field_dict["options"] = options
        if mode is not UNSET:
            field_dict["mode"] = mode

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.connect_in_credentials_type_0 import ConnectInCredentialsType0  # noqa: PLC0415
        from ..models.connect_in_options_type_0 import ConnectInOptionsType0  # noqa: PLC0415

        d = dict(src_dict)
        integration = d.pop("integration")

        def _parse_credentials(data: object) -> ConnectInCredentialsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                credentials_type_0 = ConnectInCredentialsType0.from_dict(data)

                return credentials_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ConnectInCredentialsType0 | None | Unset, data)

        credentials = _parse_credentials(d.pop("credentials", UNSET))

        def _parse_options(data: object) -> ConnectInOptionsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                options_type_0 = ConnectInOptionsType0.from_dict(data)

                return options_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ConnectInOptionsType0 | None | Unset, data)

        options = _parse_options(d.pop("options", UNSET))

        mode = d.pop("mode", UNSET)

        connect_in = cls(
            integration=integration,
            credentials=credentials,
            options=options,
            mode=mode,
        )

        return connect_in
