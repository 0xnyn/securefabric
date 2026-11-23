from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.passthrough_out_headers import PassthroughOutHeaders


T = TypeVar("T", bound="PassthroughOut")


@_attrs_define
class PassthroughOut:
    """
    Attributes:
        status (int | None):
        headers (PassthroughOutHeaders):
        body (Any):
        truncated (bool):  Default: False.
        error (None | str):
    """

    status: int | None
    headers: PassthroughOutHeaders
    body: Any
    error: None | str
    truncated: bool = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status: int | None
        status = self.status

        headers = self.headers.to_dict()

        body = self.body

        truncated = self.truncated

        error: None | str
        error = self.error

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "status": status,
                "headers": headers,
                "body": body,
                "truncated": truncated,
                "error": error,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.passthrough_out_headers import PassthroughOutHeaders  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_status(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        status = _parse_status(d.pop("status"))

        headers = PassthroughOutHeaders.from_dict(d.pop("headers"))

        body = d.pop("body")

        truncated = d.pop("truncated")

        def _parse_error(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        error = _parse_error(d.pop("error"))

        passthrough_out = cls(
            status=status,
            headers=headers,
            body=body,
            truncated=truncated,
            error=error,
        )

        passthrough_out.additional_properties = d
        return passthrough_out

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
