"""Worker liveness: upsert a row in ``fabric.worker_heartbeats`` every few seconds.

``make status`` and ``GET /api/v1/status`` read it to show which workers are online,
what queue they serve, and when they were last seen.
"""

import asyncio
import os
import socket
from datetime import UTC, datetime

from securefabric_core import get_logger
from securefabric_db import AsyncPool
from securefabric_worker import __version__

log = get_logger(__name__)

INTERVAL_SECONDS = 5.0


async def beat(pool: AsyncPool, worker_id: str, queue: str, concurrency: int) -> None:
    started = datetime.now(UTC)
    while True:
        try:
            async with pool.connection() as conn:
                await conn.execute(
                    """
                    insert into fabric.worker_heartbeats (
                        worker_id, queue, hostname, pid, version, concurrency,
                        started_at, last_seen_at
                    ) values (%s, %s, %s, %s, %s, %s, %s, now())
                    on conflict (worker_id) do update set last_seen_at = now(),
                        queue = excluded.queue, concurrency = excluded.concurrency
                    """,
                    (
                        worker_id,
                        queue,
                        socket.gethostname(),
                        os.getpid(),
                        __version__,
                        concurrency,
                        started,
                    ),
                )
        except Exception as exc:  # the DB blipping must never kill the worker
            log.warning("heartbeat_failed", error=type(exc).__name__)
        await asyncio.sleep(INTERVAL_SECONDS)


async def clear(pool: AsyncPool, worker_id: str) -> None:
    try:
        async with pool.connection() as conn:
            await conn.execute(
                "delete from fabric.worker_heartbeats where worker_id = %s", (worker_id,)
            )
    except Exception as exc:
        log.warning("heartbeat_clear_failed", error=type(exc).__name__)
