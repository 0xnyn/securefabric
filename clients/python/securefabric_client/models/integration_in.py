from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.integration_in_option_defaults_type_0 import IntegrationInOptionDefaultsType0
    from ..models.integration_in_stream_intervals_type_0 import IntegrationInStreamIntervalsType0


T = TypeVar("T", bound="IntegrationIn")


@_attrs_define
class IntegrationIn:
    """
    Attributes:
        connector_id (str):
        key (None | str | Unset):
        display_name (None | str | Unset):
        vendor_app_id (None | Unset | UUID):
        enabled_streams (list[str] | None | Unset):
        stream_intervals (IntegrationInStreamIntervalsType0 | None | Unset):
        option_defaults (IntegrationInOptionDefaultsType0 | None | Unset):
        write_back_enabled (bool | Unset):  Default: False.
    """

    connector_id: str
    key: None | str | Unset = UNSET
    display_name: None | str | Unset = UNSET
    vendor_app_id: None | Unset | UUID = UNSET
    enabled_streams: list[str] | None | Unset = UNSET
    stream_intervals: IntegrationInStreamIntervalsType0 | None | Unset = UNSET
    option_defaults: IntegrationInOptionDefaultsType0 | None | Unset = UNSET
    write_back_enabled: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        from ..models.integration_in_option_defaults_type_0 import IntegrationInOptionDefaultsType0  # noqa: PLC0415
        from ..models.integration_in_stream_intervals_type_0 import IntegrationInStreamIntervalsType0  # noqa: PLC0415

        connector_id = self.connector_id

        key: None | str | Unset
        if isinstance(self.key, Unset):
            key = UNSET
        else:
            key = self.key

        display_name: None | str | Unset
        if isinstance(self.display_name, Unset):
            display_name = UNSET
        else:
            display_name = self.display_name

        vendor_app_id: None | str | Unset
        if isinstance(self.vendor_app_id, Unset):
            vendor_app_id = UNSET
        elif isinstance(self.vendor_app_id, UUID):
            vendor_app_id = str(self.vendor_app_id)
        else:
            vendor_app_id = self.vendor_app_id

        enabled_streams: list[str] | None | Unset
        if isinstance(self.enabled_streams, Unset):
            enabled_streams = UNSET
        elif isinstance(self.enabled_streams, list):
            enabled_streams = self.enabled_streams

        else:
            enabled_streams = self.enabled_streams

        stream_intervals: dict[str, Any] | None | Unset
        if isinstance(self.stream_intervals, Unset):
            stream_intervals = UNSET
        elif isinstance(self.stream_intervals, IntegrationInStreamIntervalsType0):
            stream_intervals = self.stream_intervals.to_dict()
        else:
            stream_intervals = self.stream_intervals

        option_defaults: dict[str, Any] | None | Unset
        if isinstance(self.option_defaults, Unset):
            option_defaults = UNSET
        elif isinstance(self.option_defaults, IntegrationInOptionDefaultsType0):
            option_defaults = self.option_defaults.to_dict()
        else:
            option_defaults = self.option_defaults

        write_back_enabled = self.write_back_enabled

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "connector_id": connector_id,
            }
        )
        if key is not UNSET:
            field_dict["key"] = key
        if display_name is not UNSET:
            field_dict["display_name"] = display_name
        if vendor_app_id is not UNSET:
            field_dict["vendor_app_id"] = vendor_app_id
        if enabled_streams is not UNSET:
            field_dict["enabled_streams"] = enabled_streams
        if stream_intervals is not UNSET:
            field_dict["stream_intervals"] = stream_intervals
        if option_defaults is not UNSET:
            field_dict["option_defaults"] = option_defaults
        if write_back_enabled is not UNSET:
            field_dict["write_back_enabled"] = write_back_enabled

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.integration_in_option_defaults_type_0 import IntegrationInOptionDefaultsType0  # noqa: PLC0415
        from ..models.integration_in_stream_intervals_type_0 import IntegrationInStreamIntervalsType0  # noqa: PLC0415

        d = dict(src_dict)
        connector_id = d.pop("connector_id")

        def _parse_key(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        key = _parse_key(d.pop("key", UNSET))

        def _parse_display_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        display_name = _parse_display_name(d.pop("display_name", UNSET))

        def _parse_vendor_app_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                vendor_app_id_type_0 = UUID(data)

                return vendor_app_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        vendor_app_id = _parse_vendor_app_id(d.pop("vendor_app_id", UNSET))

        def _parse_enabled_streams(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                enabled_streams_type_0 = cast(list[str], data)

                return enabled_streams_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        enabled_streams = _parse_enabled_streams(d.pop("enabled_streams", UNSET))

        def _parse_stream_intervals(data: object) -> IntegrationInStreamIntervalsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                stream_intervals_type_0 = IntegrationInStreamIntervalsType0.from_dict(data)

                return stream_intervals_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(IntegrationInStreamIntervalsType0 | None | Unset, data)

        stream_intervals = _parse_stream_intervals(d.pop("stream_intervals", UNSET))

        def _parse_option_defaults(data: object) -> IntegrationInOptionDefaultsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                option_defaults_type_0 = IntegrationInOptionDefaultsType0.from_dict(data)

                return option_defaults_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(IntegrationInOptionDefaultsType0 | None | Unset, data)

        option_defaults = _parse_option_defaults(d.pop("option_defaults", UNSET))

        write_back_enabled = d.pop("write_back_enabled", UNSET)

        integration_in = cls(
            connector_id=connector_id,
            key=key,
            display_name=display_name,
            vendor_app_id=vendor_app_id,
            enabled_streams=enabled_streams,
            stream_intervals=stream_intervals,
            option_defaults=option_defaults,
            write_back_enabled=write_back_enabled,
        )

        return integration_in
