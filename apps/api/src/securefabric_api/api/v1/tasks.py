from uuid import UUID

from fastapi import APIRouter, Response, status

from securefabric_api.api.v1.schemas import TaskStatus
from securefabric_api.dependencies import AbsurdDep
from securefabric_core import NotFoundError
from securefabric_tasks import Queue

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", name="get_task", summary="Get the state/result of a durable task")
async def get_task(task_id: UUID, absurd: AbsurdDep, queue: Queue = Queue.DEFAULT) -> TaskStatus:
    snapshot = await absurd.fetch_task_result(str(task_id), queue_name=queue)
    if snapshot is None:
        raise NotFoundError("Task not found", task_id=str(task_id), queue=queue)
    return TaskStatus(
        task_id=str(task_id),
        queue=queue,
        state=snapshot.state,
        result=snapshot.result,
        failure=snapshot.failure,
    )


@router.post(
    "/{task_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a pending, running or sleeping task",
)
async def cancel_task(task_id: UUID, absurd: AbsurdDep, queue: Queue = Queue.DEFAULT) -> Response:
    if await absurd.fetch_task_result(str(task_id), queue_name=queue) is None:
        raise NotFoundError("Task not found", task_id=str(task_id), queue=queue)
    await absurd.cancel_task(str(task_id), queue_name=queue)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
