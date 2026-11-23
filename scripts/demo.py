"""`make demo`: trigger an on-demand sync of one connection and follow the job.

    make demo API_KEY=sfk_... CONNECTION=<connection id> [API_URL=http://localhost:8000]

Uses only the public API (POST /v1/connections/{id}/jobs, GET /v1/jobs/{id}), so it
works the same against a local API or the ngrok URL.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def call(base: str, key: str, method: str, path: str, body: Any = None) -> Any:
    req = urllib.request.Request(  # noqa: S310 - the URL is the operator's own API
        base.rstrip("/") + path,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            return json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        problem = json.loads(exc.read() or b"{}")
        sys.exit(f"{method} {path} -> {exc.code} {problem.get('code')}: {problem.get('detail')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Trigger an on-demand sync and follow the job.")
    parser.add_argument("--api-url", default=os.environ.get("API_URL", "http://localhost:8000"))
    parser.add_argument("--api-key", default=os.environ.get("API_KEY"))
    parser.add_argument("--connection", default=os.environ.get("CONNECTION"))
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    if not args.api_key or not args.connection:
        parser.error("set API_KEY and CONNECTION (or --api-key / --connection)")

    job = call(args.api_url, args.api_key, "POST", f"/v1/connections/{args.connection}/jobs", {})
    print(f"job {job['id']} ({job['type']}) {job['status']}")
    deadline = time.monotonic() + args.timeout
    last = None
    while time.monotonic() < deadline:
        job = call(args.api_url, args.api_key, "GET", f"/v1/jobs/{job['id']}")
        line = job["status"] + "".join(
            f" · {s['stream']}={s['state']}" for s in job.get("streams") or []
        )
        if line != last:
            print(f"  {line}")
            last = line
        if job["status"] not in ("QUEUED", "RUNNING"):
            print(json.dumps(job, indent=2))
            return 0 if job["status"] in ("SUCCESS", "PARTIAL") else 1
        time.sleep(1.0)
    print("still running; follow it with GET /v1/jobs/" + job["id"])
    return 1


if __name__ == "__main__":
    sys.exit(main())
