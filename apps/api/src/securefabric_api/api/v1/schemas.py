from typing import Any

from absurd_sdk import TaskResultState

from securefabric_api.schemas import ResponseModel


class TaskAccepted(ResponseModel):
    task_id: str
    run_id: str
    attempt: int
    task_name: str
    queue: str
    status_url: str


class TaskStatus(ResponseModel):
    task_id: str
    queue: str
    state: TaskResultState
    result: Any | None = None
    failure: Any | None = None
