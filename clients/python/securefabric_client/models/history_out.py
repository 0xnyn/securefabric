from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="HistoryOut")


@_attrs_define
class HistoryOut:
    """
    Attributes:
        from_state (None | str):
        to_state (str):
        at (str):
        source (str):
        stream_run_id (None | UUID):
    """

    from_state: None | str
    to_state: str
    at: str
    source: str
    stream_run_id: None | UUID
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from_state: None | str
        from_state = self.from_state

        to_state = self.to_state

        at = self.at

        source = self.source

        stream_run_id: None | str
        if isinstance(self.stream_run_id, UUID):
            stream_run_id = str(self.stream_run_id)
        else:
            stream_run_id = self.stream_run_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "from_state": from_state,
                "to_state": to_state,
                "at": at,
                "source": source,
                "stream_run_id": stream_run_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_from_state(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        from_state = _parse_from_state(d.pop("from_state"))

        to_state = d.pop("to_state")

        at = d.pop("at")

        source = d.pop("source")

        def _parse_stream_run_id(data: object) -> None | UUID:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                stream_run_id_type_0 = UUID(data)

                return stream_run_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | UUID, data)

        stream_run_id = _parse_stream_run_id(d.pop("stream_run_id"))

        history_out = cls(
            from_state=from_state,
            to_state=to_state,
            at=at,
            source=source,
            stream_run_id=stream_run_id,
        )

        history_out.additional_properties = d
        return history_out

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
