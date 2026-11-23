from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.usage_api_calls_by_hour_item import UsageApiCallsByHourItem
    from ..models.usage_daily_item import UsageDailyItem
    from ..models.usage_live import UsageLive


T = TypeVar("T", bound="Usage")


@_attrs_define
class Usage:
    """
    Attributes:
        live (UsageLive):
        daily (list[UsageDailyItem]):
        api_calls_by_hour (list[UsageApiCallsByHourItem]):
    """

    live: UsageLive
    daily: list[UsageDailyItem]
    api_calls_by_hour: list[UsageApiCallsByHourItem]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        live = self.live.to_dict()

        daily = []
        for daily_item_data in self.daily:
            daily_item = daily_item_data.to_dict()
            daily.append(daily_item)

        api_calls_by_hour = []
        for api_calls_by_hour_item_data in self.api_calls_by_hour:
            api_calls_by_hour_item = api_calls_by_hour_item_data.to_dict()
            api_calls_by_hour.append(api_calls_by_hour_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "live": live,
                "daily": daily,
                "api_calls_by_hour": api_calls_by_hour,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.usage_api_calls_by_hour_item import UsageApiCallsByHourItem  # noqa: PLC0415
        from ..models.usage_daily_item import UsageDailyItem  # noqa: PLC0415
        from ..models.usage_live import UsageLive  # noqa: PLC0415

        d = dict(src_dict)
        live = UsageLive.from_dict(d.pop("live"))

        daily = []
        _daily = d.pop("daily")
        for daily_item_data in _daily:
            daily_item = UsageDailyItem.from_dict(daily_item_data)

            daily.append(daily_item)

        api_calls_by_hour = []
        _api_calls_by_hour = d.pop("api_calls_by_hour")
        for api_calls_by_hour_item_data in _api_calls_by_hour:
            api_calls_by_hour_item = UsageApiCallsByHourItem.from_dict(api_calls_by_hour_item_data)

            api_calls_by_hour.append(api_calls_by_hour_item)

        usage = cls(
            live=live,
            daily=daily,
            api_calls_by_hour=api_calls_by_hour,
        )

        usage.additional_properties = d
        return usage

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
