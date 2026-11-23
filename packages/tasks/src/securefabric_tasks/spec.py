"""Typed task specifications on top of Absurd.

A :class:`TaskSpec` is the single source of truth for a durable task: its name,
queue, retry defaults and the pydantic models for its params and result. The API
uses it to *spawn* (validated params in) and to *read* results (validated result
out); the worker uses it to *register* a strongly-typed handler. Neither side can
drift from the other because both import the same object.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from absurd_sdk import AsyncAbsurd, AsyncTaskContext, RetryStrategy, SpawnResult
from pydantic import BaseModel

type TypedHandler[P: BaseModel, R: BaseModel] = Callable[[P, AsyncTaskContext], Awaitable[R]]


@dataclass(frozen=True, slots=True)
class TaskSpec[P: BaseModel, R: BaseModel]:
    name: str
    queue: str
    params_model: type[P]
    result_model: type[R]
    max_attempts: int = 5
    retry_strategy: RetryStrategy | None = None
    description: str = ""

    async def spawn(
        self,
        client: AsyncAbsurd,
        params: P,
        *,
        idempotency_key: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> SpawnResult:
        """Enqueue a run of this task. Works without the task being registered locally.

        IDs are normalised to ``str``: the SDK annotates them as ``str`` but psycopg
        actually returns ``uuid.UUID`` objects.
        """
        spawned = await client.spawn(
            self.name,
            params.model_dump(mode="json"),
            queue=self.queue,
            max_attempts=self.max_attempts,
            retry_strategy=self.retry_strategy,
            headers=headers,
            idempotency_key=idempotency_key,
        )
        return SpawnResult(
            task_id=str(spawned["task_id"]),
            run_id=str(spawned["run_id"]),
            attempt=int(spawned["attempt"]),
        )

    def parse_result(self, raw: Any) -> R:
        return self.result_model.model_validate(raw)

    def register(self, client: AsyncAbsurd, handler: TypedHandler[P, R]) -> None:
        """Register ``handler`` on ``client``, validating params in and results out."""

        @client.register_task(self.name, queue=self.queue, default_max_attempts=self.max_attempts)
        async def _wrapped(raw_params: Any, ctx: AsyncTaskContext) -> Any:
            params = self.params_model.model_validate(raw_params)
            result = await handler(params, ctx)
            return result.model_dump(mode="json")

        _wrapped.__name__ = getattr(handler, "__name__", self.name)
