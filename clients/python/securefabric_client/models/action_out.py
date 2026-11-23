from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.action_out_params import ActionOutParams
    from ..models.action_out_vendor_response_type_0 import ActionOutVendorResponseType0


T = TypeVar("T", bound="ActionOut")


@_attrs_define
class ActionOut:
    """
    Attributes:
        id (UUID):
        connection_id (UUID):
        finding_id (UUID):
        name (str):
        params (ActionOutParams):
        status (str):
        vendor_response (ActionOutVendorResponseType0 | None):
        message (None | str):
        created_at (datetime.datetime):
        finished_at (datetime.datetime | None):
    """

    id: UUID
    connection_id: UUID
    finding_id: UUID
    name: str
    params: ActionOutParams
    status: str
    vendor_response: ActionOutVendorResponseType0 | None
    message: None | str
    created_at: datetime.datetime
    finished_at: datetime.datetime | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.action_out_vendor_response_type_0 import ActionOutVendorResponseType0  # noqa: PLC0415

        id = str(self.id)

        connection_id = str(self.connection_id)

        finding_id = str(self.finding_id)

        name = self.name

        params = self.params.to_dict()

        status = self.status

        vendor_response: dict[str, Any] | None
        if isinstance(self.vendor_response, ActionOutVendorResponseType0):
            vendor_response = self.vendor_response.to_dict()
        else:
            vendor_response = self.vendor_response

        message: None | str
        message = self.message

        created_at = self.created_at.isoformat()

        finished_at: None | str
        if isinstance(self.finished_at, datetime.datetime):
            finished_at = self.finished_at.isoformat()
        else:
            finished_at = self.finished_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "connection_id": connection_id,
                "finding_id": finding_id,
                "name": name,
                "params": params,
                "status": status,
                "vendor_response": vendor_response,
                "message": message,
                "created_at": created_at,
                "finished_at": finished_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.action_out_params import ActionOutParams  # noqa: PLC0415
        from ..models.action_out_vendor_response_type_0 import ActionOutVendorResponseType0  # noqa: PLC0415

        d = dict(src_dict)
        id = UUID(d.pop("id"))

        connection_id = UUID(d.pop("connection_id"))

        finding_id = UUID(d.pop("finding_id"))

        name = d.pop("name")

        params = ActionOutParams.from_dict(d.pop("params"))

        status = d.pop("status")

        def _parse_vendor_response(data: object) -> ActionOutVendorResponseType0 | None:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                vendor_response_type_0 = ActionOutVendorResponseType0.from_dict(data)

                return vendor_response_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ActionOutVendorResponseType0 | None, data)

        vendor_response = _parse_vendor_response(d.pop("vendor_response"))

        def _parse_message(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        message = _parse_message(d.pop("message"))

        created_at = datetime.datetime.fromisoformat(d.pop("created_at"))

        def _parse_finished_at(data: object) -> datetime.datetime | None:
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                finished_at_type_0 = datetime.datetime.fromisoformat(data)

                return finished_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None, data)

        finished_at = _parse_finished_at(d.pop("finished_at"))

        action_out = cls(
            id=id,
            connection_id=connection_id,
            finding_id=finding_id,
            name=name,
            params=params,
            status=status,
            vendor_response=vendor_response,
            message=message,
            created_at=created_at,
            finished_at=finished_at,
        )

        action_out.additional_properties = d
        return action_out

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
