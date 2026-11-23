"""Tenant-scoped transactions (docs/plan/02-data-model.md, section 1).

Every tenant query runs inside :func:`tenant_tx`, which sets the transaction-local
``app.environment_id`` that every RLS policy compares against. A query that
forgets its ``environment_id`` filter still cannot see another tenant's rows,
and a transaction with no setting sees nothing at all (fails closed).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from securefabric_db.pool import AsyncPool

type Conn = AsyncConnection[Any]


async def set_tenant(conn: Conn, environment_id: UUID | str) -> None:
    await conn.execute("select set_config('app.environment_id', %s, true)", (str(environment_id),))


@asynccontextmanager
async def tenant_tx(pool: AsyncPool, environment_id: UUID | str) -> AsyncIterator[Conn]:
    """A transaction bound to one environment. Commits on success."""
    async with pool.connection() as conn, conn.transaction():
        await set_tenant(conn, environment_id)
        yield conn


@asynccontextmanager
async def system_tx(pool: AsyncPool) -> AsyncIterator[Conn]:
    """A transaction with no tenant binding. Only useful on an ``sf_system`` pool
    (bypassrls) or for global tables (connector catalogue, CVE mirror)."""
    async with pool.connection() as conn, conn.transaction():
        yield conn


async def fetch_all(conn: Conn, query: Any, params: Any = None) -> list[dict[str, Any]]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        return await cur.fetchall()


async def fetch_one(conn: Conn, query: Any, params: Any = None) -> dict[str, Any] | None:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        return await cur.fetchone()


async def fetch_required(conn: Conn, query: Any, params: Any = None) -> dict[str, Any]:
    """One row that must exist (an update ... returning on a row we just locked)."""
    row = await fetch_one(conn, query, params)
    if row is None:
        raise LookupError("expected a row, got none")
    return row


async def fetch_val(conn: Conn, query: Any, params: Any = None) -> Any:
    async with conn.cursor() as cur:
        await cur.execute(query, params)
        row = await cur.fetchone()
        return row[0] if row else None
