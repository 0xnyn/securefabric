"""Connections (a customer's account at a vendor), their syncs, Connect sessions and logs.

Syncs are durable: the API records a RUNNING job and spawns ``sync-connection``; the
worker finishes it. Without a worker running, jobs stay RUNNING (``make status``
flags them as stuck).
"""

from fastapi import APIRouter, Request, Response, status

from securefabric_api.api.v1._util import no_content
from securefabric_api.dependencies import AbsurdDep, ConnDep
from securefabric_core import get_logger
from securefabric_domain import service
from securefabric_domain.models import (
    ConnectionCreate,
    ConnectionPatch,
    ConnectSession,
    ConnectSessionCreate,
    Created,
    CredentialsUpdate,
    HealthSimulation,
    OperationCreate,
    SyncStarted,
)
from securefabric_domain.repository import Conn
from securefabric_tasks import SYNC_CONNECTION, SyncConnectionParams

log = get_logger(__name__)

router = APIRouter(prefix="/environments/{env}/connections", tags=["connections"])
sessions = APIRouter(prefix="/environments/{env}/connect-sessions", tags=["connect"])
operations = APIRouter(prefix="/environments/{env}/operations", tags=["operations"])


async def spawn_sync(
    conn: Conn,
    absurd: AbsurdDep,
    request: Request,
    connection_id: str,
    job_id: str,
    seconds: float,
) -> str | None:
    """Hand a recorded job to the worker. If it can't be queued, fail the job visibly."""
    try:
        spawned = await SYNC_CONNECTION.spawn(
            absurd,
            SyncConnectionParams(
                connection_id=connection_id, job_id=job_id, duration_seconds=seconds
            ),
            idempotency_key=f"sync:{job_id}",
            headers={"request_id": request.headers.get("x-request-id", "")},
        )
    except Exception as exc:
        log.warning("sync_enqueue_failed", job_id=job_id, error=str(exc))
        await service.fail_sync(conn, connection_id, job_id, "Couldn't queue the sync task")
        return None
    await service.attach_task(conn, job_id, spawned["task_id"])
    return spawned["task_id"]


@router.post("", name="create_connection", status_code=status.HTTP_201_CREATED)
async def create_connection(
    env: str, body: ConnectionCreate, conn: ConnDep, absurd: AbsurdDep, request: Request
) -> SyncStarted:
    """Create a connection and start its initial sync."""
    connection_id, job_id = await service.create_connection(conn, env, body)
    task_id = await spawn_sync(
        conn, absurd, request, connection_id, job_id, service.INITIAL_SYNC_SECONDS
    )
    return SyncStarted(connection_id=connection_id, job_id=job_id, task_id=task_id)


@router.post("/{connection_id}/sync", name="trigger_sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    env: str, connection_id: str, conn: ConnDep, absurd: AbsurdDep, request: Request
) -> SyncStarted:
    """Sync now. A connection with revoked credentials fails at once (no task)."""
    job_id, outcome = await service.trigger_sync(conn, env, connection_id)
    task_id = (
        await spawn_sync(
            conn, absurd, request, connection_id, job_id, service.ON_DEMAND_SYNC_SECONDS
        )
        if outcome == "started"
        else None
    )
    return SyncStarted(connection_id=connection_id, job_id=job_id, task_id=task_id)


@router.patch("/{connection_id}", name="update_connection", status_code=status.HTTP_204_NO_CONTENT)
async def update_connection(
    env: str, connection_id: str, body: ConnectionPatch, conn: ConnDep
) -> Response:
    """Pause/resume, override the schedule or webhook URL, edit tags and metadata."""
    await service.update_connection(conn, env, connection_id, body)
    return no_content()


@router.put(
    "/{connection_id}/credentials",
    name="update_credentials",
    status_code=status.HTTP_202_ACCEPTED,
)
async def update_credentials(
    env: str,
    connection_id: str,
    body: CredentialsUpdate,
    conn: ConnDep,
    absurd: AbsurdDep,
    request: Request,
) -> SyncStarted:
    """Replace credentials (stored masked) and re-sync."""
    job_id = await service.update_credentials(conn, env, connection_id, body.values)
    task_id = await spawn_sync(
        conn, absurd, request, connection_id, job_id, service.ON_DEMAND_SYNC_SECONDS
    )
    return SyncStarted(connection_id=connection_id, job_id=job_id, task_id=task_id)


@router.post(
    "/{connection_id}/health", name="simulate_health", status_code=status.HTTP_204_NO_CONTENT
)
async def simulate_health(
    env: str, connection_id: str, body: HealthSimulation, conn: ConnDep
) -> Response:
    """Simulate a vendor-side change, e.g. the customer revoking access."""
    await service.simulate_health(conn, env, connection_id, body.health)
    return no_content()


@router.delete("/{connection_id}", name="delete_connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(env: str, connection_id: str, conn: ConnDep) -> Response:
    await service.delete_connection(conn, env, connection_id)
    return no_content()


@sessions.post("", name="create_connect_session", status_code=status.HTTP_201_CREATED)
async def create_connect_session(
    env: str, body: ConnectSessionCreate, conn: ConnDep
) -> ConnectSession:
    """A short-lived link your customer opens to connect their account."""
    return await service.create_connect_session(conn, env, body)


@operations.post("", name="record_operation", status_code=status.HTTP_201_CREATED)
async def record_operation(env: str, body: OperationCreate, conn: ConnDep) -> Created:
    """Append a log entry (the dash records API calls made from its playground)."""
    return Created(id=await service.record_operation(conn, env, body))
