"""Spike S12 / M10 benchmark: Absurd under SecureFabric's pattern.

Thousands of short tasks per minute: spawn N tasks into a throwaway queue, drain
them with C concurrent claimers (claim batches, complete each run), then time the
retention cleanup. Reports spawn rate, completion throughput, claim latency
percentiles and cleanup cost. Runs against TEST_DATABASE_URL (never the dev DB)
and drops its queue afterwards.

    uv run python tools/bench/absurd_load.py --tasks 5000 --concurrency 1,4,8
"""

import argparse
import asyncio
import json
import os
import statistics
import time
import uuid

import psycopg

DEFAULT_URL = "postgresql://securefabric:securefabric@localhost:5432/securefabric_test"


async def spawn(url: str, queue: str, n: int, batch: int = 500) -> float:
    started = time.perf_counter()
    async with await psycopg.AsyncConnection.connect(url) as conn:
        for i in range(0, n, batch):
            async with conn.transaction():
                for j in range(i, min(n, i + batch)):
                    await conn.execute(
                        "select absurd.spawn_task(%s, 'bench.noop', %s, %s)",
                        (
                            queue,
                            json.dumps({"i": j}),
                            json.dumps({"max_attempts": 3, "idempotency_key": f"bench:{j}"}),
                        ),
                    )
    return time.perf_counter() - started


async def claimer(url: str, queue: str, worker: str, qty: int, latencies: list[float]) -> int:
    done = 0
    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as conn:
        while True:
            t0 = time.perf_counter()
            cur = await conn.execute(
                "select run_id from absurd.claim_task(%s, %s, 60, %s)", (queue, worker, qty)
            )
            runs = await cur.fetchall()
            latencies.append(time.perf_counter() - t0)
            if not runs:
                return done
            for (run_id,) in runs:
                await conn.execute(
                    "select absurd.complete_run(%s, %s, %s)", (queue, run_id, json.dumps({"ok": 1}))
                )
                done += 1


async def drain(url: str, queue: str, concurrency: int, qty: int) -> tuple[float, int, list[float]]:
    latencies: list[float] = []
    started = time.perf_counter()
    counts = await asyncio.gather(
        *(claimer(url, queue, f"bench-{k}", qty, latencies) for k in range(concurrency))
    )
    return time.perf_counter() - started, sum(counts), latencies


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p * len(ordered)))]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=int, default=5000)
    parser.add_argument("--concurrency", default="1,4,8")
    parser.add_argument("--batch", type=int, default=10, help="tasks per claim")
    parser.add_argument("--url", default=os.environ.get("TEST_DATABASE_URL", DEFAULT_URL))
    args = parser.parse_args()
    assert "test" in args.url, "benchmarks run against a test database only"

    results = []
    for c in (int(x) for x in args.concurrency.split(",")):
        queue = f"bench_{uuid.uuid4().hex[:8]}"
        async with await psycopg.AsyncConnection.connect(args.url, autocommit=True) as conn:
            await conn.execute("select absurd.create_queue(%s)", (queue,))
        try:
            spawn_s = await spawn(args.url, queue, args.tasks)
            drain_s, done, lat = await drain(args.url, queue, c, args.batch)
            async with await psycopg.AsyncConnection.connect(args.url, autocommit=True) as conn:
                t0 = time.perf_counter()
                cur = await conn.execute(
                    "select absurd.cleanup_tasks(%s, 0, %s)", (queue, args.tasks * 2)
                )
                row = await cur.fetchone()
                cleaned = row[0] if row else 0
                cleanup_s = time.perf_counter() - t0
        finally:
            async with await psycopg.AsyncConnection.connect(args.url, autocommit=True) as conn:
                await conn.execute("select absurd.drop_queue(%s)", (queue,))
        results.append(
            {
                "concurrency": c,
                "tasks": args.tasks,
                "completed": done,
                "spawn_per_s": round(args.tasks / spawn_s),
                "complete_per_s": round(done / drain_s),
                "per_minute": round(done / drain_s * 60),
                "claim_ms_p50": round(pct(lat, 0.5) * 1000, 2),
                "claim_ms_p95": round(pct(lat, 0.95) * 1000, 2),
                "claim_ms_mean": round(statistics.fmean(lat) * 1000, 2) if lat else 0,
                "cleanup_s": round(cleanup_s, 3),
                "cleaned": cleaned,
            }
        )
        print(json.dumps(results[-1]))


if __name__ == "__main__":
    asyncio.run(main())
