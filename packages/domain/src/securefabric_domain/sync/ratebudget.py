"""Shared vendor rate budgets (RATE-03, RATE-04).

One ``sync.rate_bucket`` row per budget key (GitHub: the installation). Workers
do not take a database round trip per request: they lease a block of tokens in
one ``update``, spend them locally and return what is left. After every response
the vendor's own ``remaining``/``reset`` headers correct the bucket down: the
vendor is the truth, the bucket a prediction that keeps us from needing it.

Below 10% remaining, scheduled work stops and only interactive work continues.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from securefabric_cdk.errors import RateLimited
from securefabric_cdk.http import PARK_THRESHOLD_S
from securefabric_core.clock import Clock
from securefabric_db import AsyncPool, fetch_one

LEASE_BLOCK = 50
PROACTIVE_FRACTION = 0.10
MAX_SHORT_WAITS = 8  # after this many in-process waits, park instead of spinning


class DbRateBudget:
    def __init__(
        self,
        pool: AsyncPool,
        key: str,
        *,
        per_hour: int | None,
        per_second: float,
        clock: Clock,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._pool = pool
        self.key = key
        self._capacity = float(per_hour or 5000)
        self._refill = self._capacity / 3600.0
        self._min_gap = 1.0 / per_second if per_second > 0 else 0.0
        self._clock = clock
        self._sleep = sleep
        self._local = 0.0
        self._last_request = 0.0
        self._ensured = False

    async def _ensure(self) -> None:
        if self._ensured:
            return
        async with self._pool.connection() as conn:
            await conn.execute(
                """insert into sync.rate_bucket (key, capacity, tokens, refill_per_s) values (%s, %s, %s, %s)
                   on conflict (key) do nothing""",
                (self.key, self._capacity, self._capacity, self._refill),
            )
        self._ensured = True

    async def acquire(self, cost: int, *, interactive: bool) -> None:
        await self._ensure()
        waits = 0
        while self._local < cost:
            block = max(LEASE_BLOCK, cost)
            async with self._pool.connection() as conn:
                row = await fetch_one(
                    conn,
                    """
                    with refilled as (
                        select key, least(capacity, tokens + refill_per_s *
                               extract(epoch from (clock_timestamp() - updated_at))) as t, capacity,
                               vendor_remaining, vendor_limit, reset_at
                          from sync.rate_bucket where key = %(k)s for update
                    )
                    update sync.rate_bucket b
                       set tokens = case when r.t >= %(c)s and not %(throttle)s then r.t - least(r.t, %(n)s) else r.t
                           end,
                           updated_at = clock_timestamp()
                      from refilled r
                     where b.key = r.key
                    returning r.t as available, r.capacity, r.vendor_remaining, r.vendor_limit, r.reset_at,
                              case when r.t >= %(c)s and not %(throttle)s then least(r.t, %(n)s) else 0 end as granted
                    """,
                    {"k": self.key, "c": cost, "n": block, "throttle": False},
                )
            assert row is not None
            granted = float(row["granted"])
            # Proactive throttling (RATE-04): keep the last 10% for interactive work.
            fraction = None
            if row["vendor_remaining"] is not None and row["vendor_limit"]:
                fraction = row["vendor_remaining"] / row["vendor_limit"]
            elif row["capacity"]:
                fraction = float(row["available"]) / float(row["capacity"])
            if not interactive and fraction is not None and fraction < PROACTIVE_FRACTION:
                await self._give_back(granted)
                reset = row["reset_at"] or (
                    self._clock.now()
                    + timedelta(seconds=(self._capacity * PROACTIVE_FRACTION) / self._refill)
                )
                raise RateLimited(
                    reset, "rate budget below 10%; scheduled work waits for the reset"
                )
            if granted >= cost:
                self._local += granted
                break
            wait = (cost - float(row["available"])) / self._refill if self._refill else 60.0
            if row["reset_at"] is not None:
                wait = (
                    max(wait, 0.0)
                    if row["reset_at"] <= self._clock.now()
                    else min(wait, (row["reset_at"] - self._clock.now()).total_seconds())
                )
            waits += 1
            if wait > PARK_THRESHOLD_S or waits > MAX_SHORT_WAITS:
                raise RateLimited(self._clock.now() + timedelta(seconds=max(wait, 1.0)))
            await self._sleep(max(wait, 0.05))
        self._local -= cost
        if self._min_gap:
            gap = time.monotonic() - self._last_request
            if gap < self._min_gap:
                await self._sleep(self._min_gap - gap)
            self._last_request = time.monotonic()

    async def observe(
        self, *, remaining: int | None, limit: int | None, reset_at: datetime | None
    ) -> None:
        if remaining is None and limit is None:
            return
        async with self._pool.connection() as conn:
            await conn.execute(
                """update sync.rate_bucket
                      set tokens = least(tokens, coalesce(%s::float - %s::float, tokens)),
                          vendor_remaining = coalesce(%s, vendor_remaining),
                          vendor_limit = coalesce(%s, vendor_limit),
                          capacity = coalesce(%s::float, capacity),
                          refill_per_s = coalesce(%s::float / 3600.0, refill_per_s),
                          reset_at = coalesce(%s, reset_at),
                          updated_at = clock_timestamp()
                    where key = %s""",
                (
                    remaining,
                    self._local if remaining is not None else 0,
                    remaining,
                    limit,
                    limit,
                    limit,
                    reset_at,
                    self.key,
                ),
            )
        if limit:
            self._capacity = float(limit)
            self._refill = self._capacity / 3600.0
        if remaining is not None:
            self._local = min(self._local, float(remaining))

    async def _give_back(self, tokens: float) -> None:
        if tokens <= 0:
            return
        async with self._pool.connection() as conn:
            await conn.execute(
                "update sync.rate_bucket set tokens = least(capacity, tokens + %s) where key = %s",
                (tokens, self.key),
            )

    async def release(self) -> None:
        local, self._local = self._local, 0.0
        await self._give_back(local)
