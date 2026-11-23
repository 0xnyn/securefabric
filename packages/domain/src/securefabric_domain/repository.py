"""Reads: Postgres rows → the snapshot the dash renders.

``load_workspace`` assembles one :class:`~securefabric_domain.models.Workspace` with
a fixed number of queries (no N+1), trimming jobs to 40 per connection and
operations to 800 per environment, newest first, as the dash expects.
"""

import secrets
import string
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, LiteralString

from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row

from securefabric_core import NotFoundError
from securefabric_domain.models import (
    ApiKey,
    Connection,
    ConnectSettings,
    Customer,
    Environment,
    EnvKeys,
    EnvVariable,
    Integration,
    Member,
    Operation,
    SyncJob,
    Team,
    User,
    Webhook,
    Workspace,
)

type Conn = AsyncConnection[Any]
type Row = dict[str, Any]
type Query = LiteralString | sql.SQL | sql.Composed

SNAPSHOT_VERSION = 4
MAX_JOBS_PER_CONNECTION = 40
MAX_OPERATIONS_PER_ENVIRONMENT = 800

_ID_ALPHABET = string.ascii_lowercase + string.digits


def make_id(prefix: str, length: int = 10) -> str:
    """``conn_7f3k9q2m1x``: the prefixed IDs the dash shows."""
    return f"{prefix}_{''.join(secrets.choice(_ID_ALPHABET) for _ in range(length))}"


def make_secret(prefix: str, length: int = 32) -> str:
    return f"{prefix}{''.join(secrets.choice(_ID_ALPHABET) for _ in range(length))}"


def ms(value: datetime | None) -> int | None:
    return None if value is None else int(value.timestamp() * 1000)


def ms_required(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def from_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=UTC)


async def fetch_all(conn: Conn, query: Query, params: Any = None) -> list[Row]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        return await cur.fetchall()


async def fetch_one(conn: Conn, query: Query, params: Any = None) -> Row | None:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        return await cur.fetchone()


async def environment_row(conn: Conn, slug: str) -> Row:
    row = await fetch_one(conn, "select * from fabric.environments where slug = %s", (slug,))
    if row is None:
        raise NotFoundError("Environment not found", environment=slug)
    return row


async def connection_row(conn: Conn, env_id: str, connection_id: str) -> Row:
    row = await fetch_one(
        conn,
        "select * from fabric.connections where environment_id = %s and id = %s",
        (env_id, connection_id),
    )
    if row is None:
        raise NotFoundError("Connection not found", connection=connection_id)
    return row


async def integration_row(conn: Conn, env_id: str, integration_id: str) -> Row:
    row = await fetch_one(
        conn,
        "select * from fabric.integrations where environment_id = %s and id = %s",
        (env_id, integration_id),
    )
    if row is None:
        raise NotFoundError("Integration not found", integration=integration_id)
    return row


# --- Row → model -----------------------------------------------------------------


def _job(row: Row) -> SyncJob:
    return SyncJob(
        added=row["added"],
        deleted=row["deleted"],
        duration_ms=row["duration_ms"],
        failure_reason=row["failure_reason"],
        id=row["id"],
        started_at=ms_required(row["started_at"]),
        status=row["status"],
        type=row["type"],
        updated=row["updated"],
    )


def _connection(row: Row, jobs: list[SyncJob]) -> Connection:
    return Connection(
        counts=row["counts"],
        created_at=ms_required(row["created_at"]),
        credentials=row["credentials"],
        customer=Customer.model_validate(row["customer"]),
        domain=row["domain"],
        frequency_override=row["frequency_override"],
        health=row["health"],
        id=row["id"],
        integration_id=row["integration_id"],
        jobs=jobs,
        last_sync_at=ms(row["last_sync_at"]),
        metadata=row["metadata"],
        paused=row["paused"],
        provider=row["provider"],
        sandbox=row["sandbox"],
        tags=row["tags"],
        webhook_override=row["webhook_override"],
    )


def _operation(row: Row) -> Operation:
    return Operation(
        action=row["action"],
        connection_id=row["connection_id"],
        customer=row["customer"],
        duration_ms=row["duration_ms"],
        id=row["id"],
        integration_id=row["integration_id"],
        method=row["method"],
        path=row["path"],
        provider=row["provider"],
        records=row["records"],
        started_at=ms_required(row["started_at"]),
        status=row["status"],
        status_code=row["status_code"],
        type=row["type"],
    )


def _integration(row: Row) -> Integration:
    return Integration(
        allow_sandbox=row["allow_sandbox"],
        created_at=ms_required(row["created_at"]),
        display_name=row["display_name"],
        id=row["id"],
        models=row["models"],
        provider=row["provider"],
        sync_frequency=row["sync_frequency"],
        write_scopes=row["write_scopes"],
    )


def _api_key(row: Row) -> ApiKey:
    return ApiKey(
        created_at=ms_required(row["created_at"]),
        created_by=row["created_by"],
        id=row["id"],
        is_default=row["is_default"],
        last_used_at=ms(row["last_used_at"]),
        name=row["name"],
        preview=row["preview"],
        scopes=row["scopes"],
    )


def api_key_model(row: Row) -> ApiKey:
    return _api_key(row)


def _webhook(row: Row) -> Webhook:
    return Webhook(
        created_at=ms_required(row["created_at"]),
        description=row["description"],
        disabled=row["disabled"],
        events=row["events"],
        id=row["id"],
        url=row["url"],
    )


def _member(row: Row) -> Member:
    return Member(
        email=row["email"],
        id=row["id"],
        joined_at=ms(row["joined_at"]),
        name=row["name"],
        role=row["role"],
    )


# --- Snapshot ----------------------------------------------------------------------


async def load_workspace(conn: Conn) -> Workspace | None:
    """The whole workspace, or None before it has been seeded."""
    ws = await fetch_one(conn, "select * from fabric.workspace where id = 1")
    if ws is None:
        return None

    members = await fetch_all(conn, "select * from fabric.members order by created_at, id")
    envs = await fetch_all(conn, "select * from fabric.environments order by created_at, id")
    keys = await fetch_all(conn, "select * from fabric.api_keys order by created_at, id")
    integrations = await fetch_all(
        conn, "select * from fabric.integrations order by created_at, id"
    )
    connections = await fetch_all(
        conn, "select * from fabric.connections order by created_at desc, id"
    )
    jobs = await fetch_all(
        conn,
        """
        select * from (
            select j.*, row_number() over (
                partition by j.connection_id order by j.started_at desc, j.id desc
            ) as rn
            from fabric.sync_jobs j
        ) ranked
        where rn <= %s
        order by started_at desc, id desc
        """,
        (MAX_JOBS_PER_CONNECTION,),
    )
    operations = await fetch_all(
        conn,
        """
        select * from (
            select o.*, row_number() over (
                partition by o.environment_id order by o.started_at desc, o.id desc
            ) as rn
            from fabric.operations o
        ) ranked
        where rn <= %s
        order by started_at desc, id desc
        """,
        (MAX_OPERATIONS_PER_ENVIRONMENT,),
    )
    webhooks = await fetch_all(conn, "select * from fabric.webhooks order by created_at, id")
    variables = await fetch_all(conn, "select * from fabric.variables order by created_at, key")

    jobs_by_conn: dict[str, list[SyncJob]] = defaultdict(list)
    for row in jobs:
        jobs_by_conn[row["connection_id"]].append(_job(row))

    by_env: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    for row in keys:
        by_env[row["environment_id"]]["keys"].append(_api_key(row))
    for row in integrations:
        by_env[row["environment_id"]]["integrations"].append(_integration(row))
    for row in connections:
        by_env[row["environment_id"]]["connections"].append(
            _connection(row, jobs_by_conn.get(row["id"], []))
        )
    for row in operations:
        by_env[row["environment_id"]]["operations"].append(_operation(row))
    for row in webhooks:
        by_env[row["environment_id"]]["webhooks"].append(_webhook(row))
    for row in variables:
        by_env[row["environment_id"]]["variables"].append(
            EnvVariable(key=row["key"], secret=row["secret"], value=row["value"])
        )

    environments = [
        Environment(
            api_keys=by_env[e["id"]]["keys"],
            callback_url=e["callback_url"],
            connect=ConnectSettings.model_validate(e["connect"]),
            connections=by_env[e["id"]]["connections"],
            created_at=ms_required(e["created_at"]),
            id=e["id"],
            integrations=by_env[e["id"]]["integrations"],
            is_production=e["is_production"],
            keys=EnvKeys(
                rotated_at=ms_required(e["keys_rotated_at"]), secret=e["default_key_secret"]
            ),
            name=e["name"],
            operations=by_env[e["id"]]["operations"],
            slug=e["slug"],
            variables=by_env[e["id"]]["variables"],
            webhook_secret=e["webhook_secret"],
            webhooks=by_env[e["id"]]["webhooks"],
        )
        for e in envs
    ]

    return Workspace(
        environments=environments,
        members=[_member(m) for m in members],
        seeded_at=ms_required(ws["seeded_at"]),
        team=Team(name=ws["team_name"], plan=ws["team_plan"], slug=ws["team_slug"]),
        user=User(email=ws["user_email"], name=ws["user_name"]),
        version=SNAPSHOT_VERSION,
    )
