"""Task contracts: params/result schemas and specs for every durable task.

Retries of *classified* failures are ours (PD-13): a stream slice that hits a
vendor 5xx ends its Absurd task normally and the run row waits for its next
attempt on our schedule. Absurd's own ``max_attempts`` only covers a worker
dying mid-task.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from securefabric_tasks.queues import Queue
from securefabric_tasks.spec import TaskSpec


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SliceParams(_Params):
    run_id: str
    environment_id: str
    slice: int = 0


class SliceResult(BaseModel):
    run_id: str
    outcome: str
    health_code: str | None = None


SYNC_SLICE_INTERACTIVE = TaskSpec(
    name="sync.slice",
    queue=Queue.SYNC_INTERACTIVE,
    params_model=SliceParams,
    result_model=SliceResult,
    max_attempts=20,
    description="Execute one slice of one stream run (interactive pool).",
)
SYNC_SLICE_BULK = TaskSpec(
    name="sync.slice",
    queue=Queue.SYNC_BULK,
    params_model=SliceParams,
    result_model=SliceResult,
    max_attempts=20,
    description="Execute one slice of one stream run (bulk pool).",
)


class VerifyParams(_Params):
    connection_id: str
    environment_id: str
    reason: Literal["create", "test", "rotate", "reprobe", "reauthorize", "restore"] = "create"
    staged: bool = False


class VerifyResultModel(BaseModel):
    connection_id: str
    is_valid: bool
    message: str | None = None
    grants: dict[str, str] = Field(default_factory=dict)


CONNECTION_VERIFY = TaskSpec(
    name="connection.verify",
    queue=Queue.CONTROL,
    params_model=VerifyParams,
    result_model=VerifyResultModel,
    max_attempts=3,
    retry_strategy={"kind": "exponential", "base_seconds": 2, "factor": 2, "max_seconds": 30},
    description="Verify credentials, probe streams, record grants, activate.",
)


class ConnectCompleteParams(_Params):
    state: str
    environment_id: str


CONNECT_COMPLETE = TaskSpec(
    name="connect.complete",
    queue=Queue.CONTROL,
    params_model=ConnectCompleteParams,
    result_model=VerifyResultModel,
    max_attempts=2,
    description="Finish a redirect connect flow: exchange the code, check access, bind, verify.",
)


class IngressParams(_Params):
    delivery_row_id: str


class GenericResult(BaseModel):
    ok: bool = True
    detail: dict[str, Any] = Field(default_factory=dict)


INGRESS_PROCESS = TaskSpec(
    name="ingress.process",
    queue=Queue.CONTROL,
    params_model=IngressParams,
    result_model=GenericResult,
    max_attempts=5,
    description="Route an inbound vendor webhook and apply its effects.",
)


class ActionParams(_Params):
    action_id: str
    environment_id: str


ACTION_PERFORM = TaskSpec(
    name="action.perform",
    queue=Queue.CONTROL,
    params_model=ActionParams,
    result_model=GenericResult,
    max_attempts=1,
    description="Perform a write-back action against the vendor.",
)


class DeliveryParams(_Params):
    delivery_id: str
    environment_id: str


DELIVERY_SEND = TaskSpec(
    name="webhook.deliver",
    queue=Queue.DELIVERY,
    params_model=DeliveryParams,
    result_model=GenericResult,
    max_attempts=3,
    description="Deliver one outbound webhook with its retry schedule (durable sleeps).",
)


class MaintenanceParams(_Params):
    job: str
    args: dict[str, Any] = Field(default_factory=dict)


MAINTENANCE_RUN = TaskSpec(
    name="maintenance.run",
    queue=Queue.MAINTENANCE,
    params_model=MaintenanceParams,
    result_model=GenericResult,
    max_attempts=3,
    description="Retention, partitions, purge, refresh sweeps, enrichment.",
)

ALL_TASKS: tuple[TaskSpec[Any, Any], ...] = (
    SYNC_SLICE_INTERACTIVE,
    SYNC_SLICE_BULK,
    CONNECTION_VERIFY,
    CONNECT_COMPLETE,
    INGRESS_PROCESS,
    ACTION_PERFORM,
    DELIVERY_SEND,
    MAINTENANCE_RUN,
)
