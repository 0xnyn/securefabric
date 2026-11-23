"""Benchmark gate: outbox delivery (NFR-03: 99% of events delivered within 60 s).

Emits N events into the outbox (in bursts, as syncs finishing would), then runs the
real pipeline: scheduler ticks dispatch the outbox (one delivery per event x endpoint,
spawned in the same transaction), delivery workers claim and send signed requests to
an in-process receiver that timestamps each arrival. Reports the latency from emit to
receipt.

    uv run python tools/bench/outbox.py --events 2000 --workers 4
"""

import argparse
import asyncio
import json
import os
import time
from typing import Any
from uuid import UUID

from securefabric_cdk.inprocess import InProcessTransport, VendorRequest, VendorResponse
from securefabric_db import fetch_all
from securefabric_domain import tenancy
from securefabric_domain.events.delivery import deliver_with_retries
from securefabric_domain.events.endpoints import create_endpoint
from securefabric_domain.events.outbox import emit
from securefabric_domain.sync.scheduler import Scheduler
from securefabric_domain.testing import build_test_platform, make_tenant, reset_queues

DEFAULT_URL = "postgresql://securefabric:securefabric@localhost:5432/securefabric_test"


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(p * len(s)))] if s else 0.0


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--url", default=os.environ.get("TEST_DATABASE_URL", DEFAULT_URL))
    args = ap.parse_args()
    assert "test" in args.url, "benchmarks run against a test database only"
    p = build_test_platform(args.url)
    await p.open()
    received: dict[str, float] = {}

    def receiver(req: VendorRequest) -> VendorResponse:
        received[json.loads(req.body)["id"]] = time.time()
        return VendorResponse(200, {"ok": True})

    p.webhook_transport = lambda: InProcessTransport(receiver)
    try:
        await reset_queues(p)
        tenant = await make_tenant(p)
        principal = tenancy.system_principal(tenant.environment_id, tenant.account_id)
        await create_endpoint(
            p,
            principal,
            url="https://example.com/hooks",
            description="bench",
            event_types=["sync.completed"],
        )
        emitted: dict[str, float] = {}
        from securefabric_db import tenant_tx

        for i in range(0, args.events, 100):  # bursts of 100, like a busy minute of syncs
            async with tenant_tx(p.pool, tenant.environment_id) as conn:
                for j in range(i, min(args.events, i + 100)):
                    ev = await emit(
                        conn,
                        environment_id=tenant.environment_id,
                        type="sync.completed",
                        data={"n": j},
                    )
                    emitted[ev["id"]] = time.time()

        scheduler = Scheduler(p)
        scheduler.maintenance_enabled = False

        async def delivery_worker(k: int) -> None:
            # Runs until everything arrived (bounded by --timeout). Exiting on idle once
            # stranded the run when a slow first tick had not dispatched anything yet.
            while len(received) < len(emitted):
                async with p.sys_pool.connection() as conn:
                    tasks = await fetch_all(
                        conn,
                        "select * from absurd.claim_task('delivery', %s, 300, 20)",
                        (f"bench-{k}",),
                    )
                if not tasks:
                    await asyncio.sleep(0.05)
                    continue
                for t in tasks:
                    res: Any = await deliver_with_retries(
                        p,
                        UUID(t["params"]["environment_id"]),
                        UUID(t["params"]["delivery_id"]),
                    )
                    async with p.sys_pool.connection() as conn:
                        await conn.execute(
                            "select absurd.complete_run('delivery', %s, %s)",
                            (t["run_id"], json.dumps(res, default=str)),
                        )

        async def dispatcher() -> None:
            while len(received) < len(emitted):
                await scheduler.tick()
                await asyncio.sleep(0.2)

        t0 = time.perf_counter()
        try:
            await asyncio.wait_for(
                asyncio.gather(dispatcher(), *(delivery_worker(k) for k in range(args.workers))),
                timeout=args.timeout,
            )
        except TimeoutError:
            async with p.sys_pool.connection() as conn:
                diag = {
                    "deliveries": await fetch_all(
                        conn,
                        "select status, count(*) as n from events.webhook_delivery group by 1",
                    ),
                    "undispatched": await fetch_all(
                        conn,
                        "select count(*) as n from events.outbox_event where dispatched_at is null",
                    ),
                    "received": len(received),
                }
            print(json.dumps({"timeout": True, **diag}, default=str))
            raise
        elapsed = time.perf_counter() - t0
        lat = [received[e] - emitted[e] for e in emitted if e in received]
        within = sum(1 for x in lat if x <= 60) / len(emitted)
        print(
            json.dumps(
                {
                    "events": len(emitted),
                    "delivered": len(lat),
                    "seconds": round(elapsed, 1),
                    "per_s": round(len(lat) / elapsed),
                    "latency_p50_s": round(pct(lat, 0.5), 2),
                    "latency_p99_s": round(pct(lat, 0.99), 2),
                    "within_60s": round(within, 4),
                    "gate_99pct_within_60s": within >= 0.99,
                }
            )
        )
    finally:
        await reset_queues(p)
        await p.close()


if __name__ == "__main__":
    asyncio.run(main())
