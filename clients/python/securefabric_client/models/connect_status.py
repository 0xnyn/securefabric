from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.connect_status_grants_item import ConnectStatusGrantsItem
    from ..models.verification import Verification


T = TypeVar("T", bound="ConnectStatus")


@_attrs_define
class ConnectStatus:
    """
    Attributes:
        id (UUID):
        state (str):
        health_code (str):
        pending_detail (None | str):
        grants (list[ConnectStatusGrantsItem]):
        missing_permissions (list[str]):
        last_verification (None | Verification):
    """

    id: UUID
    state: str
    health_code: str
    pending_detail: None | str
    grants: list[ConnectStatusGrantsItem]
    missing_permissions: list[str]
    last_verification: None | Verification
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.verification import Verification  # noqa: PLC0415

        id = str(self.id)

        state = self.state

        health_code = self.health_code

        pending_detail: None | str
        pending_detail = self.pending_detail

        grants = []
        for grants_item_data in self.grants:
            grants_item = grants_item_data.to_dict()
            grants.append(grants_item)

        missing_permissions = self.missing_permissions

        last_verification: dict[str, Any] | None
        if isinstance(self.last_verification, Verification):
            last_verification = self.last_verification.to_dict()
        else:
            last_verification = self.last_verification

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "state": state,
                "health_code": health_code,
                "pending_detail": pending_detail,
                "grants": grants,
                "missing_permissions": missing_permissions,
                "last_verification": last_verification,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.connect_status_grants_item import ConnectStatusGrantsItem  # noqa: PLC0415
        from ..models.verification import Verification  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        state = d.pop("state")

        health_code = d.pop("health_code")

        def _parse_pending_detail(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        pending_detail = _parse_pending_detail(d.pop("pending_detail"))

        grants = []
        _grants = d.pop("grants")
        for grants_item_data in _grants:
            grants_item = ConnectStatusGrantsItem.from_dict(grants_item_data)

            grants.append(grants_item)

        missing_permissions = cast(list[str], d.pop("missing_permissions"))

        def _parse_last_verification(data: object) -> None | Verification:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                last_verification_type_0 = Verification.from_dict(data)

                return last_verification_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Verification, data)

        last_verification = _parse_last_verification(d.pop("last_verification"))

        connect_status = cls(
            id=id,
            state=state,
            health_code=health_code,
            pending_detail=pending_detail,
            grants=grants,
            missing_permissions=missing_permissions,
            last_verification=last_verification,
        )

        connect_status.additional_properties = d
        return connect_status

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
