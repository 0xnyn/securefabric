"""Connection syncs: the durable half of "Sync now" and of every new connection.

The API records a RUNNING job and spawns ``sync-connection``. This handler sleeps
durably for the (simulated) vendor sync, then completes the job in one
transaction (counts, health, logs, webhooks). ``finish_sync`` is idempotent, so
an Absurd retry or replay after a crash can't double-apply it.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from absurd_sdk import AsyncAbsurd, AsyncTaskContext

from securefabric_core import get_logger
from securefabric_db import AsyncPool
from securefabric_domain import service
from securefabric_tasks import SYNC_CONNECTION, SyncConnectionParams, SyncConnectionResult

log = get_logger(__name__)


def make_handler(
    pool: AsyncPool,
) -> Callable[[SyncConnectionParams, AsyncTaskContext], Awaitable[SyncConnectionResult]]:
    async def sync_connection(
        params: SyncConnectionParams, ctx: AsyncTaskContext
    ) -> SyncConnectionResult:
        bound = log.bind(
            task_id=str(ctx.task_id), connection_id=params.connection_id, job_id=params.job_id
        )
        if params.duration_seconds:
            # Stand-in for paging through the vendor API. Durable: a worker restart
            # resumes here instead of starting the sync over.
            await ctx.sleep_for("vendor-sync", params.duration_seconds)

        async def finish() -> dict[str, Any]:
            async with pool.connection() as conn:
                return await service.finish_sync(conn, params.connection_id, params.job_id)

        outcome: dict[str, Any] = await ctx.step("finish", finish)
        bound.info("connection_synced", **{k: v for k, v in outcome.items() if k != "jobId"})
        return SyncConnectionResult(
            job_id=params.job_id,
            status=outcome["status"],
            added=int(outcome.get("added", 0)),
            updated=int(outcome.get("updated", 0)),
            deleted=int(outcome.get("deleted", 0)),
        )

    return sync_connection


def register(client: AsyncAbsurd, pool: AsyncPool) -> None:
    SYNC_CONNECTION.register(client, make_handler(pool))
