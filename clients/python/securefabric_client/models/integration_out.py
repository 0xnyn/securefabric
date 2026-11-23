from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.integration_out_capabilities import IntegrationOutCapabilities
    from ..models.integration_out_option_defaults import IntegrationOutOptionDefaults
    from ..models.integration_out_options_schema import IntegrationOutOptionsSchema
    from ..models.integration_out_stream_intervals import IntegrationOutStreamIntervals


T = TypeVar("T", bound="IntegrationOut")


@_attrs_define
class IntegrationOut:
    """
    Attributes:
        id (UUID):
        key (str):
        connector_id (str):
        connector_version (str):
        deprecated (bool):
        display_name (str):
        vendor_app_id (None | UUID):
        enabled_streams (list[str]):
        stream_intervals (IntegrationOutStreamIntervals):
        option_defaults (IntegrationOutOptionDefaults):
        options_schema (IntegrationOutOptionsSchema):
        write_back_enabled (bool):
        capabilities (IntegrationOutCapabilities):
        created_at (datetime.datetime):
    """

    id: UUID
    key: str
    connector_id: str
    connector_version: str
    deprecated: bool
    display_name: str
    vendor_app_id: None | UUID
    enabled_streams: list[str]
    stream_intervals: IntegrationOutStreamIntervals
    option_defaults: IntegrationOutOptionDefaults
    options_schema: IntegrationOutOptionsSchema
    write_back_enabled: bool
    capabilities: IntegrationOutCapabilities
    created_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = str(self.id)

        key = self.key

        connector_id = self.connector_id

        connector_version = self.connector_version

        deprecated = self.deprecated

        display_name = self.display_name

        vendor_app_id: None | str
        if isinstance(self.vendor_app_id, UUID):
            vendor_app_id = str(self.vendor_app_id)
        else:
            vendor_app_id = self.vendor_app_id

        enabled_streams = self.enabled_streams

        stream_intervals = self.stream_intervals.to_dict()

        option_defaults = self.option_defaults.to_dict()

        options_schema = self.options_schema.to_dict()

        write_back_enabled = self.write_back_enabled

        capabilities = self.capabilities.to_dict()

        created_at = self.created_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "key": key,
                "connector_id": connector_id,
                "connector_version": connector_version,
                "deprecated": deprecated,
                "display_name": display_name,
                "vendor_app_id": vendor_app_id,
                "enabled_streams": enabled_streams,
                "stream_intervals": stream_intervals,
                "option_defaults": option_defaults,
                "options_schema": options_schema,
                "write_back_enabled": write_back_enabled,
                "capabilities": capabilities,
                "created_at": created_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.integration_out_capabilities import IntegrationOutCapabilities  # noqa: PLC0415
        from ..models.integration_out_option_defaults import IntegrationOutOptionDefaults  # noqa: PLC0415
        from ..models.integration_out_options_schema import IntegrationOutOptionsSchema  # noqa: PLC0415
        from ..models.integration_out_stream_intervals import IntegrationOutStreamIntervals  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        key = d.pop("key")

        connector_id = d.pop("connector_id")

        connector_version = d.pop("connector_version")

        deprecated = d.pop("deprecated")

        display_name = d.pop("display_name")

        def _parse_vendor_app_id(data: object) -> None | UUID:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                vendor_app_id_type_0 = UUID(data)

                return vendor_app_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        vendor_app_id = _parse_vendor_app_id(d.pop("vendor_app_id"))

        enabled_streams = cast(list[str], d.pop("enabled_streams"))

        stream_intervals = IntegrationOutStreamIntervals.from_dict(d.pop("stream_intervals"))

        option_defaults = IntegrationOutOptionDefaults.from_dict(d.pop("option_defaults"))

        options_schema = IntegrationOutOptionsSchema.from_dict(d.pop("options_schema"))

        write_back_enabled = d.pop("write_back_enabled")

        capabilities = IntegrationOutCapabilities.from_dict(d.pop("capabilities"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        integration_out = cls(
            id=id,
            key=key,
            connector_id=connector_id,
            connector_version=connector_version,
            deprecated=deprecated,
            display_name=display_name,
            vendor_app_id=vendor_app_id,
            enabled_streams=enabled_streams,
            stream_intervals=stream_intervals,
            option_defaults=option_defaults,
            options_schema=options_schema,
            write_back_enabled=write_back_enabled,
            capabilities=capabilities,
            created_at=created_at,
        )

        integration_out.additional_properties = d
        return integration_out

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
