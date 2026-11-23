from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.repair_task_state import RepairTaskState

if TYPE_CHECKING:
    from ..models.repair_failure import RepairFailure
    from ..models.repair_task_result_type_0 import RepairTaskResultType0


T = TypeVar("T", bound="RepairTask")


@_attrs_define
class RepairTask:
    """
    Attributes:
        task_id (str):
        state (RepairTaskState):
        result (None | RepairTaskResultType0):
        failure (None | RepairFailure):
    """

    task_id: str
    state: RepairTaskState
    result: None | RepairTaskResultType0
    failure: None | RepairFailure
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.repair_failure import RepairFailure  # noqa: PLC0415
        from ..models.repair_task_result_type_0 import RepairTaskResultType0  # noqa: PLC0415

        task_id = self.task_id

        state = self.state.value

        result: dict[str, Any] | None
        if isinstance(self.result, RepairTaskResultType0):
            result = self.result.to_dict()
        else:
            result = self.result

        failure: dict[str, Any] | None
        if isinstance(self.failure, RepairFailure):
            failure = self.failure.to_dict()
        else:
            failure = self.failure

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "task_id": task_id,
                "state": state,
                "result": result,
                "failure": failure,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.repair_failure import RepairFailure  # noqa: PLC0415
        from ..models.repair_task_result_type_0 import RepairTaskResultType0  # noqa: PLC0415

        d = dict(src_dict)
        task_id = d.pop("task_id")

        state = RepairTaskState(d.pop("state"))

        def _parse_result(data: object) -> None | RepairTaskResultType0:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                result_type_0 = RepairTaskResultType0.from_dict(data)

                return result_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | RepairTaskResultType0, data)

        result = _parse_result(d.pop("result"))

        def _parse_failure(data: object) -> None | RepairFailure:
            if data is None:
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                failure_type_0 = RepairFailure.from_dict(data)

                return failure_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | RepairFailure, data)

        failure = _parse_failure(d.pop("failure"))

        repair_task = cls(
            task_id=task_id,
            state=state,
            result=result,
            failure=failure,
        )

        repair_task.additional_properties = d
        return repair_task

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
