"""System status: one source for ``GET /v1/status``, ``make status`` and the dash.

``collect`` reads the operational facts through ``obs.system_status()`` (a narrow
SECURITY DEFINER function, so it works under the least-privileged API role) and
compares the applied migrations with the files on disk.

``view`` decides what a caller sees:

- **public** (no credentials): overall status, version, whether the database answers.
- **customer** (any authenticated principal): also workers (without host names or
  process ids), queue depths, active run counts and open-alert counts by severity.
- **operator**: everything, including host names and the open alerts themselves
  (alert subjects name run, connection and app ids across tenants).
"""

import time
from pathlib import Path
from typing import Any, Literal

from psycopg import AsyncConnection

from securefabric_db import fetch_one
from securefabric_db.migrate import DEFAULT_MIGRATIONS_DIR, MigrationError, discover

Audience = Literal["public", "customer", "operator"]

# A queue whose oldest pending task waited longer than this means no worker is draining it.
QUEUE_LAG_SECONDS = 60


def _on_disk(migrations_dir: Path | None) -> list[str] | None:
    path = migrations_dir or Path(DEFAULT_MIGRATIONS_DIR)
    try:
        return [m.version for m in discover(path)]
    except MigrationError:
        return None  # running outside the repository: nothing to compare against


async def collect(
    conn: AsyncConnection[Any], *, version: str, migrations_dir: Path | None = None
) -> dict[str, Any]:
    """Every fact, for the operator view. Raises if the database cannot be queried."""
    t0 = time.perf_counter()
    row = await fetch_one(conn, "select obs.system_status() as s")
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    facts: dict[str, Any] = (row or {}).get("s") or {}
    applied: list[str] = facts.pop("migrations", [])
    on_disk = _on_disk(migrations_dir)
    pending = [v for v in on_disk if v not in applied] if on_disk is not None else []
    migrations: dict[str, Any] = {
        "applied": applied,
        "pending": pending,
        "unknown": [v for v in applied if v not in on_disk] if on_disk is not None else [],
        "compared_with_disk": on_disk is not None,
    }
    workers = facts.get("workers", [])
    queues = facts.get("queues", [])
    problems: list[str] = []
    if pending:
        problems.append(f"{len(pending)} migration(s) pending")
    if not any(w["online"] for w in workers):
        problems.append("no worker online")
    lagging = [
        q["name"] for q in queues if (q.get("oldest_pending_seconds") or 0) > QUEUE_LAG_SECONDS
    ]
    if lagging:
        problems.append(f"queue lag: {', '.join(lagging)}")
    if facts.get("stuck_runs"):
        problems.append(f"{facts['stuck_runs']} run(s) RUNNING for over 15 minutes")
    if (facts.get("alert_counts") or {}).get("page"):
        problems.append(f"{facts['alert_counts']['page']} paging alert(s) open")
    return {
        "status": "degraded" if problems else "ok",
        "problems": problems,
        "version": version,
        "database": {"reachable": True, "latency_ms": latency_ms, **facts.get("database", {})},
        "migrations": migrations,
        "workers": workers,
        "queues": queues,
        "runs": facts.get("runs", {}),
        "stuck_runs": facts.get("stuck_runs", 0),
        "failed_runs_last_day": facts.get("failed_runs_last_day", 0),
        "alert_counts": facts.get("alert_counts", {}),
        "alerts": facts.get("alerts", []),
    }


def down(version: str, error: BaseException) -> dict[str, Any]:
    return {
        "status": "down",
        "problems": ["database unreachable"],
        "version": version,
        "database": {"reachable": False, "error": type(error).__name__},
        "migrations": {},
        "workers": [],
        "queues": [],
        "runs": {},
        "stuck_runs": 0,
        "failed_runs_last_day": 0,
        "alert_counts": {},
        "alerts": [],
    }


_WORKER_PUBLIC = ("worker_id", "role", "queues", "version", "concurrency", "online", "last_seen_at")


def view(facts: dict[str, Any], audience: Audience) -> dict[str, Any]:
    """What ``audience`` may see of ``facts`` (see the module docstring)."""
    if audience == "operator":
        return facts
    db = facts.get("database", {})
    if audience == "public":
        return {
            "status": facts["status"],
            "problems": [],
            "version": facts["version"],
            "database": {"reachable": db.get("reachable", False)},
            "migrations": {},
            "workers": [],
            "queues": [],
            "runs": {},
            "stuck_runs": 0,
            "failed_runs_last_day": 0,
            "alert_counts": {},
            "alerts": [],
        }
    return {
        **facts,
        "database": {k: v for k, v in db.items() if k != "size_bytes"},
        "workers": [{k: w.get(k) for k in _WORKER_PUBLIC} for w in facts.get("workers", [])],
        "alerts": [],  # subjects identify other tenants' runs; counts stay in alert_counts
    }
