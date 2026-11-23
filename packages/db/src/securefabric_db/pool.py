"""Async psycopg connection pool helpers.

Each process connects with the migrating login and immediately ``SET ROLE``s to
its application role (part 9, section 2), so row-level security and column
grants apply exactly as they would with separate logins:

- ``sf_api``     the API: RLS, no access to wrapped private keys
- ``sf_worker``  sync, control and delivery workers: RLS, may read wrapped keys
- ``sf_system``  scheduler and retention: ``bypassrls``, cross-tenant
"""

from typing import Any, Literal

from psycopg import AsyncConnection, sql
from psycopg_pool import AsyncConnectionPool

from securefabric_db.settings import DatabaseSettings

type AsyncPool = AsyncConnectionPool[AsyncConnection[Any]]
type AppRole = Literal["sf_api", "sf_worker", "sf_system"]


def create_pool(
    settings: DatabaseSettings,
    *,
    role: AppRole | None = None,
    name: str = "securefabric",
    min_size: int | None = None,
    max_size: int | None = None,
) -> AsyncPool:
    """Create (but do not open) an async pool whose connections run as ``role``.

    Connections are autocommit because Absurd's stored procedures manage their own
    transactional semantics, and it keeps simple reads free of idle transactions.
    Use :func:`securefabric_db.tenant_tx` for tenant-scoped transactions.
    """

    async def configure(conn: AsyncConnection[Any]) -> None:
        if role is not None:
            await conn.execute(sql.SQL("set role {}").format(sql.Identifier(role)))
        # A batch transaction must never outlive the 5-second org-feed guard (part 4, 7).
        await conn.execute("set statement_timeout = '60s'")

    return AsyncConnectionPool(
        conninfo=settings.url,
        min_size=settings.pool_min_size if min_size is None else min_size,
        max_size=settings.pool_max_size if max_size is None else max_size,
        timeout=settings.pool_timeout,
        kwargs={"autocommit": True, "connect_timeout": settings.connect_timeout},
        configure=configure,
        open=False,
        name=f"{name}:{role or 'owner'}",
    )


async def ping(pool: AsyncPool) -> bool:
    """Return True if the database answers a trivial query."""
    try:
        async with pool.connection() as conn:
            await conn.execute("select 1")
    except Exception:
        return False
    return True
