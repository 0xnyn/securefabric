"""Async psycopg connection pool helpers."""

from typing import Any

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from securefabric_db.settings import DatabaseSettings

type AsyncPool = AsyncConnectionPool[AsyncConnection[Any]]


def create_pool(settings: DatabaseSettings) -> AsyncPool:
    """Create (but do not open) an async pool.

    Connections are autocommit because Absurd's stored procedures manage their own
    transactional semantics, and it keeps simple reads free of idle transactions.
    """
    return AsyncConnectionPool(
        conninfo=settings.url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        timeout=settings.pool_timeout,
        kwargs={"autocommit": True, "connect_timeout": settings.connect_timeout},
        open=False,
        name="securefabric",
    )


async def ping(pool: AsyncPool) -> bool:
    """Return True if the database answers a trivial query."""
    try:
        async with pool.connection() as conn:
            await conn.execute("select 1")
    except Exception:
        return False
    return True
