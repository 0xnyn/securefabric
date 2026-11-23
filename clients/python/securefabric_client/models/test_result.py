from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.test_result_grants import TestResultGrants


T = TypeVar("T", bound="TestResult")


@_attrs_define
class TestResult:
    """
    Attributes:
        is_valid (bool):
        message (None | str):
        grants (TestResultGrants):
        pending (bool):  Default: False.
    """

    is_valid: bool
    message: None | str
    grants: TestResultGrants
    pending: bool = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        is_valid = self.is_valid

        message: None | str
        message = self.message

        grants = self.grants.to_dict()

        pending = self.pending

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "is_valid": is_valid,
                "message": message,
                "grants": grants,
                "pending": pending,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.test_result_grants import TestResultGrants  # noqa: PLC0415

        d = dict(src_dict)
        is_valid = d.pop("is_valid")

        def _parse_message(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        message = _parse_message(d.pop("message"))

        grants = TestResultGrants.from_dict(d.pop("grants"))

        pending = d.pop("pending")

        test_result = cls(
            is_valid=is_valid,
            message=message,
            grants=grants,
            pending=pending,
        )

        test_result.additional_properties = d
        return test_result

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
