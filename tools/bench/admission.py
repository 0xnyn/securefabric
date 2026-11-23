"""Benchmark gate: admission (docs/plan/10-delivery-plan.md, section 8).

Target: 200 admitted runs a second, admission lag under 5 s. Queues on-demand jobs
for many SANDBOX connections across many environments (so caps are not the limit),
then runs the real scheduler's admission (each admit also spawns the Absurd task in
the same transaction) until everything admissible is admitted.

    uv run python tools/bench/admission.py --environments 50 --connections 10
"""

import argparse
import asyncio
import json
import os
import time

from securefabric_db import fetch_all, system_tx, tenant_tx
from securefabric_domain.sync import jobs
from securefabric_domain.sync.bundle import budget_key_for
from securefabric_domain.sync.scheduler import Scheduler
from securefabric_domain.testing import (
    build_test_platform,
    make_connection,
    make_tenant,
    reset_queues,
)

DEFAULT_URL = "postgresql://securefabric:securefabric@localhost:5432/securefabric_test"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--environments", type=int, default=50)
    ap.add_argument("--connections", type=int, default=10, help="per environment")
    ap.add_argument("--url", default=os.environ.get("TEST_DATABASE_URL", DEFAULT_URL))
    ap.add_argument(
        "--uncapped",
        action="store_true",
        help="lift queue/global caps (sync.concurrency_limit) to measure admission itself",
    )
    args = ap.parse_args()
    assert "test" in args.url, "benchmarks run against a test database only"
    p = build_test_platform(args.url)
    await p.open()
    try:
        await reset_queues(p)
        queued = 0
        for e in range(args.environments):
            tenant = await make_tenant(p, name=f"adm-{e}")
            for c in range(args.connections):
                cid = await make_connection(
                    p, tenant, credentials={"api_key": f"sbx_adm_{e}_{c}"}, options={}
                )
                async with tenant_tx(p.pool, tenant.environment_id) as conn:
                    key = await budget_key_for(p, conn, cid)
                    await jobs.on_demand(
                        p,
                        conn,
                        cid,
                        streams=None,
                        force_full_refresh=False,
                        since=None,
                        requested_by="bench",
                        budget_key=key,
                    )
        async with system_tx(p.sys_pool) as conn:
            rows = await fetch_all(
                conn, "select count(*) as n from sync.stream_run where state = 'QUEUED'"
            )
            queued = int(rows[0]["n"])
        if args.uncapped:
            async with system_tx(p.sys_pool) as conn:
                for kind in ("queue", "global", "connector"):
                    await conn.execute(
                        """insert into sync.concurrency_limit (scope_kind, scope_id, max_running)
                           values (%s, '*', 100000)
                           on conflict (scope_kind, scope_id) do update set max_running = 100000""",
                        (kind,),
                    )
        scheduler = Scheduler(p)
        t0 = time.perf_counter()
        admitted = rounds = 0
        while True:
            n = await scheduler.admit()
            rounds += 1
            if n == 0:
                break
            admitted += n
        elapsed = time.perf_counter() - t0
        report = {
            "uncapped": args.uncapped,
            "queued": queued,
            "admitted": admitted,
            "rounds": rounds,
            "seconds": round(elapsed, 2),
            "admitted_per_s": round(admitted / elapsed) if elapsed else None,
            "gate_200_per_s": admitted / elapsed >= 200 if elapsed else False,
            "lag_under_5s": elapsed < 5 or admitted / elapsed >= 200,
        }
        print(json.dumps(report))
    finally:
        if args.uncapped:
            async with system_tx(p.sys_pool) as conn:
                await conn.execute(
                    "delete from sync.concurrency_limit where scope_id = '*' and max_running = 100000"
                )
        await reset_queues(p)
        await p.close()


if __name__ == "__main__":
    asyncio.run(main())
