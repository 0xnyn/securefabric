"""Worker process: claims tasks from one Absurd queue and runs registered handlers."""

import asyncio
import contextlib
import os
import signal
import socket

from absurd_sdk import AsyncAbsurd

from securefabric_core import configure_logging, get_logger
from securefabric_db import AsyncPool, DatabaseSettings, create_pool
from securefabric_tasks import AbsurdSettings
from securefabric_worker import heartbeat
from securefabric_worker.config import WorkerSettings
from securefabric_worker.handlers import register_all

log = get_logger(__name__)


def build_client(
    settings: WorkerSettings, db: DatabaseSettings, absurd: AbsurdSettings, pool: AsyncPool
) -> AsyncAbsurd:
    client = AsyncAbsurd(
        db.url,
        queue_name=settings.queue,
        default_max_attempts=absurd.default_max_attempts,
    )
    register_all(client, pool)
    return client


async def ensure_queue(client: AsyncAbsurd, settings: WorkerSettings) -> None:
    await client.create_queue(
        settings.queue,
        cleanup_ttl=settings.queue_cleanup_ttl,
        cleanup_limit=settings.queue_cleanup_limit,
    )
    log.info("queue_ready", queue=settings.queue, cleanup_ttl=settings.queue_cleanup_ttl)


async def run(
    settings: WorkerSettings | None = None,
    db: DatabaseSettings | None = None,
    absurd: AbsurdSettings | None = None,
) -> None:
    settings = settings or WorkerSettings()
    db = db or DatabaseSettings()
    absurd = absurd or AbsurdSettings()
    configure_logging(settings.log_level, settings.log_format)

    # Handlers read and write the control plane through their own pool.
    pool = create_pool(db)
    await pool.open(wait=False)
    client = build_client(settings, db, absurd, pool)
    worker_id = settings.worker_id or f"{socket.gethostname()}:{os.getpid()}"
    loop = asyncio.get_running_loop()

    def _shutdown(sig: signal.Signals) -> None:
        log.info("shutdown_requested", signal=sig.name)
        # Stops claiming new work; in-flight tasks in the current batch finish first.
        client.stop_worker()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    try:
        if settings.auto_create_queue:
            await ensure_queue(client, settings)
        beating = asyncio.create_task(
            heartbeat.beat(pool, worker_id, settings.queue, settings.concurrency)
        )
        log.info(
            "worker_started",
            worker_id=worker_id,
            queue=settings.queue,
            concurrency=settings.concurrency,
            environment=settings.environment,
        )
        await client.start_worker(
            worker_id=worker_id,
            claim_timeout=settings.claim_timeout,
            concurrency=settings.concurrency,
            poll_interval=settings.poll_interval,
        )
        beating.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await beating
    finally:
        await heartbeat.clear(pool, worker_id)
        await client.close()
        await pool.close()
        log.info("worker_stopped")
