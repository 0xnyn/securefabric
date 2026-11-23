"""Per-environment API rate limits (API-07).

A token bucket per environment, default 1,000 requests a minute. Counters live
in process memory and are synchronised through Postgres every second, which is
approximate across API instances but needs no extra infrastructure. The
limiter is behind this small interface in case that stops being good enough.
"""

import asyncio
import contextlib
import math
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from securefabric_core import get_logger
from securefabric_db import AsyncPool

log = get_logger(__name__)

DEFAULT_PER_MINUTE = 1000


@dataclass
class Decision:
    allowed: bool
    limit: int
    remaining: int
    reset: int  # epoch seconds


class RateLimiter:
    def __init__(self, pool: AsyncPool | None, per_minute: int = DEFAULT_PER_MINUTE) -> None:
        self._pool = pool
        self.per_minute = per_minute
        self._window = 0
        self._local: dict[str, int] = defaultdict(int)  # this window, not yet flushed
        self._global: dict[str, int] = defaultdict(int)  # all instances, as of the last sync
        self._task: asyncio.Task[None] | None = None

    def _roll(self) -> int:
        window = int(time.time() // 60)
        if window != self._window:
            self._window = window
            self._local.clear()
            self._global.clear()
        return window

    def check(self, environment_id: UUID) -> Decision:
        window = self._roll()
        key = str(environment_id)
        used = self._global[key] + self._local[key]
        reset = (window + 1) * 60
        if used >= self.per_minute:
            return Decision(False, self.per_minute, 0, reset)
        self._local[key] += 1
        return Decision(True, self.per_minute, max(0, self.per_minute - used - 1), reset)

    async def sync(self) -> None:
        if self._pool is None:
            return
        window = self._roll()
        start = datetime.fromtimestamp(window * 60, UTC)
        pending, self._local = dict(self._local), defaultdict(int)
        try:
            # One definer function (migration 0007): the API role cannot touch the
            # counter or usage tables directly.
            async with self._pool.connection() as conn, conn.transaction():
                cur = await conn.execute(
                    "select environment_id::text, calls "
                    "from obs.flush_api_calls(%s, %s::uuid[], %s::int[])",
                    (start, list(pending), list(pending.values())),
                )
                totals = await cur.fetchall()
        except Exception:
            # Keep the counts for the next attempt rather than losing them.
            for env, n in pending.items():
                self._local[env] += n
            raise
        for env, count in totals:
            self._global[env] = count

    async def run(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            try:
                await self.sync()
            except Exception as exc:
                log.warning("rate_limit_sync_failed", error=type(exc).__name__)

    def start(self) -> None:
        self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        with contextlib.suppress(Exception):
            await self.sync()


def retry_after(decision: Decision) -> int:
    return max(1, math.ceil(decision.reset - time.time()))
