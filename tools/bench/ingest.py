"""Benchmark gate: ingest throughput per worker (NFR-05: >= 2,000 records/s).

Runs a real SANDBOX backfill through the executor and the write path (hash-gated
upsert, state history, links, stream heads, outbox) in one process against the test
database, then a second unchanged pass (the steady state of incremental syncs).

    uv run python tools/bench/ingest.py --findings 20000 --page-size 500
"""

import argparse
import asyncio
import json
import os
import time

from securefabric_domain.testing import (
    build_test_platform,
    make_connection,
    make_tenant,
    reset_queues,
    sync_stream,
)
from securefabric_schema import Mode

DEFAULT_URL = "postgresql://securefabric:securefabric@localhost:5432/securefabric_test"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--findings", type=int, default=20000)
    ap.add_argument("--hosts", type=int, default=2000)
    ap.add_argument("--page-size", type=int, default=500)
    ap.add_argument("--encrypted", action="store_true", help="with STORE-09 payload keys")
    ap.add_argument("--no-reset", action="store_true", help="leave other runs alone")
    ap.add_argument("--url", default=os.environ.get("TEST_DATABASE_URL", DEFAULT_URL))
    args = ap.parse_args()
    assert "test" in args.url, "benchmarks run against a test database only"
    settings = None
    if args.encrypted:
        import base64

        from securefabric_domain.testing import build_test_settings

        key = base64.b64encode(os.urandom(32)).decode()
        settings = build_test_settings(payload_keys=f"1:{key}")
    p = build_test_platform(args.url, settings=settings)
    await p.open()
    try:
        if not args.no_reset:
            await reset_queues(p)
        tenant = await make_tenant(p)
        cid = await make_connection(
            p,
            tenant,
            credentials={"api_key": f"sbx_bench_{os.getpid()}"},
            options={
                "finding_count": args.findings,
                "host_count": args.hosts,
                "image_count": 50,
                "page_size": args.page_size,
            },
        )
        report = {"findings": args.findings, "hosts": args.hosts, "encrypted": args.encrypted}
        for stream, n in (("hosts", args.hosts), ("findings", args.findings)):
            t0 = time.perf_counter()
            out = await sync_stream(p, tenant, cid, stream, Mode.BACKFILL)
            dt = time.perf_counter() - t0
            assert out.kind == "completed", out.error
            report[f"{stream}_records_per_s"] = round(n / dt)
            report[f"{stream}_seconds"] = round(dt, 2)
        t0 = time.perf_counter()
        out = await sync_stream(p, tenant, cid, "findings", Mode.FULL)
        dt = time.perf_counter() - t0
        assert out.kind == "completed", out.error
        report["unchanged_full_pass_records_per_s"] = round(args.findings / dt)
        report["unchanged_rows_written"] = out.counts.added + out.counts.updated
        report["gate_2000_per_s"] = report["findings_records_per_s"] >= 2000
        print(json.dumps(report))
    finally:
        await p.close()


if __name__ == "__main__":
    asyncio.run(main())
