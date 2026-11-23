"""Benchmark gate: scale-out (NFR-07: doubling sync workers roughly doubles throughput).

Runs the ingest benchmark as 1 process, then as 2 concurrent processes (separate
tenants and connections, like two sync workers), and compares aggregate records per
second. "Roughly doubles" is taken as at least 1.6x.

    uv run python tools/bench/scale_out.py --findings 20000
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(n: int, findings: int) -> tuple[float, int]:
    t0 = time.perf_counter()
    procs = [
        subprocess.Popen(  # noqa: S603 - our own benchmark
            [
                sys.executable,
                str(ROOT / "tools/bench/ingest.py"),
                "--findings",
                str(findings),
                "--hosts",
                "100",
                "--no-reset",  # concurrent workers must not quiesce each other's runs
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=ROOT,
        )
        for _ in range(n)
    ]
    total = 0
    for p in procs:
        out, _ = p.communicate(timeout=1800)
        report = json.loads(out.decode().strip().splitlines()[-1])
        total += report["findings"] + report["hosts"]
    return time.perf_counter() - t0, total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--findings", type=int, default=20000)
    args = ap.parse_args()
    one_s, one_n = run(1, args.findings)
    two_s, two_n = run(2, args.findings)
    r1, r2 = one_n / one_s, two_n / two_s
    report = {
        "one_worker_records_per_s": round(r1),
        "two_workers_records_per_s": round(r2),
        "speedup": round(r2 / r1, 2),
        "gate_roughly_doubles": r2 / r1 >= 1.6,
    }
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
