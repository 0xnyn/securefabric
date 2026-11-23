"""Benchmark gates for the data API (docs/plan/10-delivery-plan.md, section 8; NFR-04).

Seeds one SANDBOX connection with N findings through the real ingest path (test
database only), starts the real API (uvicorn, port 8002) against that database, and
drives a fixed request rate per scenario, measuring latency over HTTP:

- list findings, limit 100, connection scope        p95 <= 500 ms at 50 req/s
- get finding by id                                  p95 <= 150 ms
- lastSeenSince on the large connection              p95 <= 2 s
- organization-scoped list                           p95 <= 1 s

    uv run python tools/bench/api_latency.py --findings 200000 --rate 50 --seconds 20
"""

import argparse
import asyncio
import json
import os
import random
import statistics
import time
from datetime import timedelta
from typing import Any
from urllib.parse import quote

import httpx2
import uvicorn

from securefabric_domain import tenancy
from securefabric_domain.testing import (
    build_test_platform,
    build_test_settings,
    make_connection,
    make_tenant,
    reset_queues,
    sync_stream,
)
from securefabric_schema import Mode

DEFAULT_URL = "postgresql://securefabric:securefabric@localhost:5432/securefabric_test"
PORT = 8002


def pctl(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p * len(ordered)))] if ordered else 0.0


async def drive(
    client: httpx2.AsyncClient, make_request: Any, rate: int, seconds: int
) -> dict[str, Any]:
    """Open-loop load: start one request every 1/rate s regardless of responses."""
    latencies: list[float] = []
    errors = 0

    async def one() -> None:
        nonlocal errors
        method, url, headers = make_request()
        t0 = time.perf_counter()
        r = await client.request(method, url, headers=headers)
        latencies.append(time.perf_counter() - t0)
        if r.status_code >= 400:
            errors += 1

    tasks = []
    start = time.perf_counter()
    for i in range(rate * seconds):
        delay = start + i / rate - time.perf_counter()
        if delay > 0:
            await asyncio.sleep(delay)
        tasks.append(asyncio.create_task(one()))
    await asyncio.gather(*tasks)
    return {
        "requests": len(latencies),
        "errors": errors,
        "p50_ms": round(pctl(latencies, 0.5) * 1000, 1),
        "p95_ms": round(pctl(latencies, 0.95) * 1000, 1),
        "p99_ms": round(pctl(latencies, 0.99) * 1000, 1),
        "mean_ms": round(statistics.fmean(latencies) * 1000, 1),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--findings", type=int, default=200_000)
    ap.add_argument("--rate", type=int, default=50)
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--url", default=os.environ.get("TEST_DATABASE_URL", DEFAULT_URL))
    ap.add_argument(
        "--reuse",
        action="store_true",
        help="measure an already seeded connection of this size instead of seeding again",
    )
    args = ap.parse_args()
    assert "test" in args.url, "benchmarks run against a test database only"
    os.environ["DATABASE_URL"] = args.url  # the API process below uses the test database

    worker = build_test_platform(args.url)
    await worker.open()
    t0 = time.perf_counter()
    found = None
    if args.reuse:
        import psycopg

        async with await psycopg.AsyncConnection.connect(args.url) as c:
            cur = await c.execute(
                """select c.id, c.organization_id, c.environment_id, e.account_id
                     from control.connection c join control.environment e on e.id = c.environment_id
                    where c.options->>'finding_count' = %s order by c.created_at desc limit 1""",
                (str(args.findings),),
            )
            found = await cur.fetchone()
    if found:
        from types import SimpleNamespace

        cid = found[0]
        tenant = SimpleNamespace(
            organization_id=found[1], environment_id=found[2], account_id=found[3]
        )
    else:
        await reset_queues(worker)
        tenant = await make_tenant(worker)
        cid = await make_connection(
            worker,
            tenant,
            credentials={"api_key": f"sbx_apibench_{os.getpid()}"},
            options={
                "finding_count": args.findings,
                "host_count": 2000,
                "image_count": 100,
                "page_size": 1000,
            },
        )
        for stream in ("hosts", "images", "findings"):
            out = await sync_stream(worker, tenant, cid, stream, Mode.BACKFILL)
            assert out.kind == "completed", out.error
    seed_s = time.perf_counter() - t0
    principal = tenancy.system_principal(tenant.environment_id, tenant.account_id)
    _, key = await tenancy.create_api_key(worker, principal, name="bench", scopes=None)

    from securefabric_api.main import create_app

    api_platform = build_test_platform(args.url, role="api", settings=build_test_settings())
    app = create_app(platform=api_platform, rate_limit_per_minute=10**9)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning", lifespan="on")
    )
    serving = asyncio.create_task(server.serve())
    while not server.started:  # noqa: ASYNC110 - uvicorn exposes no started event
        await asyncio.sleep(0.05)
    headers = {"Authorization": f"Bearer {key}", "X-CONNECTION-ID": str(cid)}
    org_headers = {
        "Authorization": f"Bearer {key}",
        "X-ORGANIZATION-ID": str(tenant.organization_id),
    }
    report: dict[str, Any] = {"findings": args.findings, "seed_seconds": round(seed_s, 1)}
    try:
        async with httpx2.AsyncClient(
            base_url=f"http://127.0.0.1:{PORT}",
            timeout=30,
            limits=httpx2.Limits(max_connections=200),
        ) as client:
            page = (
                await client.get("/v1/vulnerability_findings?limit=100", headers=headers)
            ).json()
            ids = [f["id"] for f in page["items"]]
            cursor = page.get("next_cursor")
            # URL-encoded: a raw "+00:00" would arrive as a space.
            since = quote((worker.clock.now() - timedelta(days=3650)).isoformat())
            scenarios = {
                "list_limit_100": (
                    lambda: ("GET", "/v1/vulnerability_findings?limit=100", headers),
                    500,
                ),
                "list_next_page": (
                    lambda: (
                        "GET",
                        f"/v1/vulnerability_findings?limit=100&cursor={cursor}",
                        headers,
                    ),
                    500,
                ),
                "get_by_id": (
                    lambda: (
                        "GET",
                        f"/v1/vulnerability_findings/{random.choice(ids)}",  # noqa: S311
                        headers,
                    ),
                    150,
                ),
                "last_seen_since": (
                    lambda: (
                        "GET",
                        f"/v1/vulnerability_findings?limit=100&lastSeenSince={since}",
                        headers,
                    ),
                    2000,
                ),
                "org_scoped_list": (
                    lambda: ("GET", "/v1/vulnerability_findings?limit=100", org_headers),
                    1000,
                ),
            }
            for name, (make, gate_ms) in scenarios.items():
                res = await drive(client, make, args.rate, args.seconds)
                res["gate_p95_ms"] = gate_ms
                res["pass"] = res["p95_ms"] <= gate_ms and res["errors"] == 0
                report[name] = res
                print(name, json.dumps(res))
    finally:
        server.should_exit = True
        await serving
        await worker.close()
    report["all_gates_pass"] = all(
        v["pass"] for v in report.values() if isinstance(v, dict) and "pass" in v
    )
    print(json.dumps({"summary": report["all_gates_pass"], "findings": args.findings}))


if __name__ == "__main__":
    asyncio.run(main())
