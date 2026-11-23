"""System status: what's running, what's applied, what needs attention.

Shared by ``GET /api/v1/status`` (the dash's Status page) and ``make status``
(``scripts/status.py``), so both report the same facts from the same queries.
"""

import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from psycopg import sql
from pydantic import Field

from securefabric_db.migrate import DEFAULT_MIGRATIONS_DIR, discover
from securefabric_domain.models import Schema
from securefabric_domain.repository import Conn, fetch_all, fetch_one, ms

Level = Literal["ok", "degraded", "down", "unknown"]

WORKER_STALE_SECONDS = 20
STUCK_JOB_SECONDS = 120

_RANK: dict[Level, int] = {"ok": 0, "unknown": 1, "degraded": 2, "down": 3}


def worst(levels: list[Level]) -> Level:
    return max(levels, key=_RANK.__getitem__) if levels else "ok"


class Component(Schema):
    name: str
    status: Level
    summary: str
    latency_ms: float | None = None


class DatabaseInfo(Schema):
    reachable: bool
    latency_ms: float | None = None
    server_version: str | None = None
    database: str | None = None
    size_bytes: int | None = None


class MigrationInfo(Schema):
    applied: list[str]
    pending: list[str]
    unknown: list[str] = Field(description="Applied in the DB but missing on disk.")


class WorkerInfo(Schema):
    worker_id: str
    queue: str
    hostname: str
    pid: int
    version: str
    concurrency: int
    started_at: int
    last_seen_at: int
    online: bool


class QueueInfo(Schema):
    name: str
    pending: int
    running: int
    sleeping: int
    completed: int
    failed: int
    cancelled: int
    oldest_pending_seconds: float | None = None


class TaskCount(Schema):
    task_name: str
    state: str
    count: int


class EnvironmentStats(Schema):
    slug: str
    name: str
    is_production: bool
    integrations: int
    connections: int
    healthy: int
    attention: int = Field(description="Unauthorized, rate limited, vendor errors, timeouts.")
    syncing: int
    paused: int
    operations_last_day: int
    failed_operations_last_day: int


class WorkspaceInfo(Schema):
    seeded: bool
    team: str | None = None
    members: int = 0
    environments: list[EnvironmentStats] = Field(default_factory=list)
    running_jobs: int = 0
    stuck_jobs: int = Field(default=0, description="RUNNING longer than 2 minutes.")
    failed_jobs_last_day: int = 0


class SystemStatus(Schema):
    status: Level
    checked_at: int
    version: str
    environment: str
    uptime_seconds: float | None = None
    components: list[Component]
    database: DatabaseInfo
    migrations: MigrationInfo | None = None
    workers: list[WorkerInfo] = Field(default_factory=list)
    queues: list[QueueInfo] = Field(default_factory=list)
    tasks: list[TaskCount] = Field(default_factory=list)
    workspace: WorkspaceInfo | None = None


def migrations_dir() -> Path:
    return Path(os.environ.get("MIGRATIONS_DIR", DEFAULT_MIGRATIONS_DIR))


async def database_info(conn: Conn) -> DatabaseInfo:
    start = time.perf_counter()
    row = await fetch_one(
        conn,
        "select current_setting('server_version') as version, current_database() as db,"
        " pg_database_size(current_database()) as size",
    )
    latency = round((time.perf_counter() - start) * 1000, 2)
    return DatabaseInfo(
        reachable=True,
        latency_ms=latency,
        server_version=row["version"] if row else None,
        database=row["db"] if row else None,
        size_bytes=row["size"] if row else None,
    )


async def migration_info(conn: Conn, directory: Path | None = None) -> MigrationInfo:
    on_disk = [m.version for m in discover(directory or migrations_dir())]
    exists = await fetch_one(conn, "select to_regclass('public.schema_migrations') as t")
    applied_rows = (
        await fetch_all(conn, "select version from public.schema_migrations order by version")
        if exists and exists["t"]
        else []
    )
    applied = [r["version"] for r in applied_rows]
    return MigrationInfo(
        applied=applied,
        pending=[v for v in on_disk if v not in applied],
        unknown=[v for v in applied if v not in on_disk],
    )


async def _has_table(conn: Conn, name: str) -> bool:
    row = await fetch_one(conn, "select to_regclass(%s) as t", (name,))
    return bool(row and row["t"])


async def worker_info(conn: Conn) -> list[WorkerInfo]:
    if not await _has_table(conn, "fabric.worker_heartbeats"):
        return []
    rows = await fetch_all(
        conn,
        "select *, extract(epoch from now() - last_seen_at) as age"
        " from fabric.worker_heartbeats order by started_at",
    )
    return [
        WorkerInfo(
            worker_id=r["worker_id"],
            queue=r["queue"],
            hostname=r["hostname"],
            pid=r["pid"],
            version=r["version"],
            concurrency=r["concurrency"],
            started_at=ms(r["started_at"]) or 0,
            last_seen_at=ms(r["last_seen_at"]) or 0,
            online=float(r["age"]) < WORKER_STALE_SECONDS,
        )
        for r in rows
    ]


async def queue_info(conn: Conn) -> tuple[list[QueueInfo], list[TaskCount]]:
    if not await _has_table(conn, "absurd.queues"):
        return [], []
    queues: list[QueueInfo] = []
    tasks: list[TaskCount] = []
    for q in await fetch_all(conn, "select queue_name from absurd.queues order by queue_name"):
        name = q["queue_name"]
        table = sql.Identifier("absurd", f"t_{name}")
        counts: dict[str, int] = {}
        for r in await fetch_all(
            conn,
            sql.SQL("select state, count(*) as n from {} group by state").format(table),
        ):
            counts[r["state"]] = r["n"]
        oldest = await fetch_one(
            conn,
            sql.SQL(
                "select extract(epoch from now() - min(enqueue_at)) as age"
                " from {} where state = 'pending'"
            ).format(table),
        )
        for r in await fetch_all(
            conn,
            sql.SQL(
                "select task_name, state, count(*) as n from {} group by task_name, state"
                " order by task_name, state"
            ).format(table),
        ):
            tasks.append(TaskCount(task_name=r["task_name"], state=r["state"], count=r["n"]))
        queues.append(
            QueueInfo(
                name=name,
                pending=counts.get("pending", 0),
                running=counts.get("running", 0),
                sleeping=counts.get("sleeping", 0),
                completed=counts.get("completed", 0),
                failed=counts.get("failed", 0),
                cancelled=counts.get("cancelled", 0),
                oldest_pending_seconds=float(oldest["age"])
                if oldest and oldest["age"] is not None
                else None,
            )
        )
    return queues, tasks


_ATTENTION = ("UNAUTHORIZED", "RATE_LIMIT_EXCEEDED", "VENDOR_SERVER_ERROR", "EXECUTION_TIMEOUT")


async def workspace_info(conn: Conn) -> WorkspaceInfo:
    if not await _has_table(conn, "fabric.workspace"):
        return WorkspaceInfo(seeded=False)
    ws = await fetch_one(conn, "select team_name from fabric.workspace where id = 1")
    if ws is None:
        return WorkspaceInfo(seeded=False)
    members = await fetch_one(conn, "select count(*) as n from fabric.members")
    envs = await fetch_all(
        conn,
        """
        select e.slug, e.name, e.is_production,
            (select count(*) from fabric.integrations i
                where i.environment_id = e.id) as integrations,
            count(c.id) as connections,
            count(c.id) filter (where c.health = 'HEALTHY') as healthy,
            count(c.id) filter (where c.health = any(%s)) as attention,
            count(c.id) filter (where c.health = 'SYNCING') as syncing,
            count(c.id) filter (where c.paused) as paused,
            (select count(*) from fabric.operations o
                where o.environment_id = e.id
                and o.started_at > now() - interval '24 hours') as ops,
            (select count(*) from fabric.operations o
                where o.environment_id = e.id and o.status = 'failed'
                and o.started_at > now() - interval '24 hours') as failed_ops
        from fabric.environments e
        left join fabric.connections c on c.environment_id = e.id
        group by e.id
        order by e.created_at
        """,
        (list(_ATTENTION),),
    )
    jobs = await fetch_one(
        conn,
        """
        select
            count(*) filter (where status = 'RUNNING') as running,
            count(*) filter (
                where status = 'RUNNING' and started_at < now() - make_interval(secs => %s)
            ) as stuck,
            count(*) filter (
                where status = 'FAILED' and started_at > now() - interval '24 hours'
            ) as failed
        from fabric.sync_jobs
        """,
        (STUCK_JOB_SECONDS,),
    )
    return WorkspaceInfo(
        seeded=True,
        team=ws["team_name"],
        members=members["n"] if members else 0,
        environments=[
            EnvironmentStats(
                slug=e["slug"],
                name=e["name"],
                is_production=e["is_production"],
                integrations=e["integrations"],
                connections=e["connections"],
                healthy=e["healthy"],
                attention=e["attention"],
                syncing=e["syncing"],
                paused=e["paused"],
                operations_last_day=e["ops"],
                failed_operations_last_day=e["failed_ops"],
            )
            for e in envs
        ],
        running_jobs=jobs["running"] if jobs else 0,
        stuck_jobs=jobs["stuck"] if jobs else 0,
        failed_jobs_last_day=jobs["failed"] if jobs else 0,
    )


def components_for(
    db: DatabaseInfo,
    migrations: MigrationInfo | None,
    workers: list[WorkerInfo],
    queues: list[QueueInfo],
    workspace: WorkspaceInfo | None,
) -> list[Component]:
    """Turn raw facts into a traffic light per component."""
    out = [
        Component(
            name="database",
            status="ok" if db.reachable else "down",
            summary=f"Postgres {db.server_version} · {db.latency_ms} ms"
            if db.reachable
            else "Postgres is unreachable",
            latency_ms=db.latency_ms,
        )
    ]
    if migrations is not None:
        out.append(
            Component(
                name="migrations",
                status="degraded" if migrations.pending or migrations.unknown else "ok",
                summary=f"{len(migrations.pending)} pending: run `make db-migrate`"
                if migrations.pending
                else f"{len(migrations.applied)} applied, up to date",
            )
        )
    online = [w for w in workers if w.online]
    out.append(
        Component(
            name="worker",
            status="ok" if online else "down",
            summary=f"{len(online)} online · concurrency {sum(w.concurrency for w in online)}"
            if online
            else "No worker online: syncs won't finish (`make dev-worker`)",
        )
    )
    backlog = sum(q.pending for q in queues)
    failed = sum(q.failed for q in queues)
    stale = max((q.oldest_pending_seconds or 0 for q in queues), default=0)
    queue_level: Level = "degraded" if stale > 60 else "ok"
    out.append(
        Component(
            name="queue",
            status=queue_level if queues else "unknown",
            summary=(
                f"{backlog} pending · {sum(q.running for q in queues)} running ·"
                f" {sum(q.sleeping for q in queues)} sleeping · {failed} failed"
            )
            if queues
            else "No Absurd queues yet (the worker creates `default` on start)",
        )
    )
    if workspace is not None:
        attention = sum(e.attention for e in workspace.environments)
        ws_level: Level = (
            "unknown" if not workspace.seeded else "degraded" if workspace.stuck_jobs else "ok"
        )
        out.append(
            Component(
                name="workspace",
                status=ws_level,
                summary=(
                    f"{sum(e.connections for e in workspace.environments)} connections across"
                    f" {len(workspace.environments)} environments · {attention} need attention"
                    + (f" · {workspace.stuck_jobs} stuck syncs" if workspace.stuck_jobs else "")
                )
                if workspace.seeded
                else "Not seeded yet (`make seed`, or open the dash)",
            )
        )
    return out


async def collect(
    conn: Conn | None,
    *,
    version: str,
    environment: str,
    started_at: float | None = None,
    error: str | None = None,
) -> SystemStatus:
    """Gather everything. ``conn`` None means the database couldn't be reached."""
    migrations: MigrationInfo | None = None
    workers: list[WorkerInfo] = []
    queues: list[QueueInfo] = []
    tasks: list[TaskCount] = []
    workspace: WorkspaceInfo | None = None
    if conn is None:
        db = DatabaseInfo(reachable=False)
    else:
        db = await database_info(conn)
        try:
            migrations = await migration_info(conn)
        except Exception:  # migrations dir missing (e.g. a trimmed image)
            migrations = None
        workers = await worker_info(conn)
        queues, tasks = await queue_info(conn)
        workspace = await workspace_info(conn)
    components = components_for(db, migrations, workers, queues, workspace)
    if error and conn is None:
        components[0] = components[0].model_copy(update={"summary": error})
    return SystemStatus(
        status=worst([c.status for c in components if c.status != "unknown"]),
        checked_at=int(datetime.now(UTC).timestamp() * 1000),
        version=version,
        environment=environment,
        uptime_seconds=round(time.monotonic() - started_at, 1) if started_at else None,
        components=components,
        database=db,
        migrations=migrations,
        workers=workers,
        queues=queues,
        tasks=tasks,
        workspace=workspace,
    )


def as_dict(status: SystemStatus) -> dict[str, Any]:
    return status.model_dump(mode="json", by_alias=True)
