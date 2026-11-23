from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="ActionIn")


@_attrs_define
class ActionIn:
    """
    Attributes:
        action (str): set_state
        state (str): OPEN | IGNORED | CLOSED
        reason (None | str | Unset): false_positive | accepted_risk | test_code | revoked
        comment (None | str | Unset):
    """

    action: str
    state: str
    reason: None | str | Unset = UNSET
    comment: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action

        state = self.state

        reason: None | str | Unset
        if isinstance(self.reason, Unset):
            reason = UNSET
        else:
            reason = self.reason

        comment: None | str | Unset
        if isinstance(self.comment, Unset):
            comment = UNSET
        else:
            comment = self.comment

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
                "state": state,
            }
        )
        if reason is not UNSET:
            field_dict["reason"] = reason
        if comment is not UNSET:
            field_dict["comment"] = comment

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = d.pop("action")

        state = d.pop("state")

        def _parse_reason(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        reason = _parse_reason(d.pop("reason", UNSET))

        def _parse_comment(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        comment = _parse_comment(d.pop("comment", UNSET))

        action_in = cls(
            action=action,
            state=state,
            reason=reason,
            comment=comment,
        )

        return action_in
