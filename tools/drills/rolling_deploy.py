"""Rolling-deploy drill (M10 exit: zero 5xx during a rolling deploy under load).

Two API processes serve the same database. A small client-side balancer routes only
to instances whose `/health/ready` passes (polled every 0.25 s) and retries a request
once on another instance when the connection itself fails, as load balancers do for
idempotent GETs. While a steady load runs, each instance in turn is sent SIGTERM
(uvicorn drains in-flight requests and stops accepting new ones), restarted, and
waited on until ready. The drill reports every non-2xx response and failed request.

    uv run python tools/drills/rolling_deploy.py --rate 30 --api-key sfk_... [--connection <id>]

Runs against DATABASE_URL (it only reads).
"""

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx2

ROOT = Path(__file__).resolve().parents[2]
PORTS = (8011, 8012)


def start(port: int) -> subprocess.Popen[bytes]:
    env = {**os.environ, "API_PORT": str(port), "API_RELOAD": "false", "API_LOG_LEVEL": "WARNING"}
    return subprocess.Popen(  # noqa: S603 - our own service entry point
        [sys.executable, "-m", "uvicorn", "securefabric_api.main:create_app", "--factory",
         "--port", str(port), "--timeout-graceful-shutdown", "20"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )  # fmt: skip


async def ready(client: httpx2.AsyncClient, port: int) -> bool:
    try:
        r = await client.get(f"http://127.0.0.1:{port}/health/ready", timeout=1)
        return r.status_code == 200
    except httpx2.HTTPError:
        return False


async def wait_ready(client: httpx2.AsyncClient, port: int) -> None:
    while not await ready(client, port):  # noqa: ASYNC110 - polling an HTTP health check
        await asyncio.sleep(0.2)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=int, default=30)
    ap.add_argument("--api-key", required=True)
    ap.add_argument("--connection")
    args = ap.parse_args()
    headers = {"Authorization": f"Bearer {args.api_key}"}
    if args.connection:
        headers["X-CONNECTION-ID"] = args.connection
    path = "/v1/vulnerability_findings?limit=20" if args.connection else "/v1/organizations"

    procs = {p: start(p) for p in PORTS}
    healthy: set[int] = set()
    stats = {"requests": 0, "ok": 0, "non_2xx": 0, "status_5xx": 0, "failed": 0, "retried": 0}
    statuses: dict[int, int] = {}
    stop = asyncio.Event()
    async with httpx2.AsyncClient(timeout=30, limits=httpx2.Limits(max_connections=100)) as client:
        for p in PORTS:
            await wait_ready(client, p)
            healthy.add(p)

        async def health_loop() -> None:
            while not stop.is_set():
                for p in PORTS:
                    (healthy.add if await ready(client, p) else healthy.discard)(p)
                await asyncio.sleep(0.25)

        rr = 0

        async def one() -> None:
            nonlocal rr
            stats["requests"] += 1
            targets = sorted(healthy)
            for attempt in range(2):
                if not targets:
                    await asyncio.sleep(0.25)
                    targets = sorted(healthy)
                    continue
                rr += 1
                port = targets[rr % len(targets)]
                try:
                    r = await client.get(f"http://127.0.0.1:{port}{path}", headers=headers)
                except (httpx2.ConnectError, httpx2.RemoteProtocolError, httpx2.ReadError):
                    healthy.discard(port)
                    targets = [t for t in targets if t != port]
                    stats["retried"] += attempt == 0
                    continue
                statuses[r.status_code] = statuses.get(r.status_code, 0) + 1
                if 200 <= r.status_code < 300:
                    stats["ok"] += 1
                else:
                    stats["non_2xx"] += 1
                    stats["status_5xx"] += r.status_code >= 500
                return
            stats["failed"] += 1

        async def load() -> None:
            tasks = []
            start_t = time.perf_counter()
            i = 0
            while not stop.is_set():
                delay = start_t + i / args.rate - time.perf_counter()
                if delay > 0:
                    await asyncio.sleep(delay)
                tasks.append(asyncio.create_task(one()))
                i += 1
            await asyncio.gather(*tasks)

        checker = asyncio.create_task(health_loop())
        loader = asyncio.create_task(load())
        await asyncio.sleep(3)
        timeline = []
        for p in PORTS:  # roll one instance at a time
            t0 = time.perf_counter()
            procs[p].send_signal(signal.SIGTERM)
            await asyncio.to_thread(procs[p].wait, 30)
            procs[p] = start(p)
            await wait_ready(client, p)
            timeline.append({"port": p, "replaced_in_s": round(time.perf_counter() - t0, 2)})
            await asyncio.sleep(3)
        stop.set()
        await loader
        checker.cancel()
    for proc in procs.values():
        proc.send_signal(signal.SIGTERM)
        proc.wait(30)
    result = {**stats, "statuses": statuses, "rollout": timeline}
    result["pass"] = stats["status_5xx"] == 0 and stats["failed"] == 0 and stats["non_2xx"] == 0
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
