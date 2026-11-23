"""The worker process: one image, several roles (docs/plan/01-architecture.md, section 1).

=============  ============================================  ==================
role           does                                          opens the vault
=============  ============================================  ==================
scheduler      schedules, admission, expiry, roll-up, outbox no
sync           connector streams (interactive + bulk pools)  yes
control        verify, connect completion, ingress, actions  yes
delivery       outbound webhooks                             signing secrets
maintenance    retention, partitions, purge, refresh sweeps  yes
all            every role in one process (local development)
=============  ============================================  ==================

On SIGTERM workers stop claiming, finish the current page, save the checkpoint
and exit; an interrupted run resumes on another worker without using an attempt.
"""

import argparse
import asyncio
import contextlib
import os
import signal
import socket
from typing import Any

from absurd_sdk import AsyncAbsurd

from securefabric_core import configure_logging, get_logger
from securefabric_core.telemetry import configure_telemetry
from securefabric_db import DatabaseSettings
from securefabric_domain.runtime import Role, build_platform
from securefabric_tasks import ROLE_QUEUES
from securefabric_worker import heartbeat
from securefabric_worker.config import WorkerSettings
from securefabric_worker.handlers import register

log = get_logger(__name__)

ROLES = ("scheduler", "sync", "control", "delivery", "maintenance")
ROLE_PLATFORM: dict[str, Role] = {
    "sync": "sync",
    "control": "control",
    "delivery": "delivery",
    "maintenance": "maintenance",
}


async def _queue_worker(
    role: str,
    queue: str,
    settings: WorkerSettings,
    db: DatabaseSettings,
    stop: asyncio.Event,
    worker_id: str,
) -> None:
    platform = build_platform(ROLE_PLATFORM.get(role, "control"), db=db)
    await platform.open()
    client = AsyncAbsurd(db.url, queue_name=queue)
    register(client, platform, queue)
    task = asyncio.create_task(
        client.start_worker(
            worker_id=f"{worker_id}:{queue}",
            claim_timeout=settings.claim_timeout,
            concurrency=settings.concurrency,
            poll_interval=settings.poll_interval,
        )
    )
    log.info("queue_worker_started", queue=queue, role=role)
    try:
        await stop.wait()
    finally:
        client.stop_worker()  # stop claiming; in-flight tasks finish their page
        with contextlib.suppress(Exception):
            await asyncio.wait_for(task, timeout=30)
        await client.close()
        await platform.close()


async def _scheduler(settings: WorkerSettings, db: DatabaseSettings, stop: asyncio.Event) -> None:
    from securefabric_domain.registry import sync_catalog
    from securefabric_domain.sync.scheduler import Scheduler

    platform = build_platform("scheduler", db=db)
    await platform.open()
    await sync_catalog(platform.sys_pool, platform.registry)
    try:
        await Scheduler(platform).run_forever(stop, interval=settings.scheduler_interval)
    finally:
        await platform.close()


async def run(settings: WorkerSettings | None = None, db: DatabaseSettings | None = None) -> None:
    settings = settings or WorkerSettings()
    db = db or DatabaseSettings()
    configure_logging(settings.log_level, settings.log_format)
    configure_telemetry(
        "securefabric-worker", environment=settings.environment
    )  # OTLP if configured
    roles = list(ROLES) if settings.role == "all" else [r.strip() for r in settings.role.split(",")]
    worker_id = settings.worker_id or f"{socket.gethostname()}:{os.getpid()}"
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    hb_platform = build_platform("maintenance", db=db, with_system_pool=False)
    await hb_platform.open()
    tasks: list[asyncio.Task[Any]] = []
    queues: list[str] = []
    for role in roles:
        if role == "scheduler":
            tasks.append(asyncio.create_task(_scheduler(settings, db, stop)))
            continue
        for queue in ROLE_QUEUES[role]:
            queues.append(str(queue))
            tasks.append(
                asyncio.create_task(_queue_worker(role, str(queue), settings, db, stop, worker_id))
            )
    beating = asyncio.create_task(
        heartbeat.beat(hb_platform.pool, worker_id, settings.role, queues, settings.concurrency)
    )
    log.info("worker_started", worker_id=worker_id, roles=roles, queues=queues)
    try:
        done, _ = await asyncio.wait(
            [*tasks, asyncio.create_task(stop.wait())], return_when=asyncio.FIRST_COMPLETED
        )
        for t in done:
            if t.exception() is not None and not stop.is_set():
                log.error("worker_component_crashed", error=repr(t.exception()))
                stop.set()
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        beating.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await beating
        await heartbeat.clear(hb_platform.pool, worker_id)
        await hb_platform.close()
        log.info("worker_stopped")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="securefabric-worker")
    parser.add_argument(
        "--role", default=None, help=f"one of {', '.join(ROLES)}, a comma list, or all"
    )
    return parser.parse_args(argv)
