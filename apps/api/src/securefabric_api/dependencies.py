"""FastAPI dependencies. Override these in tests via ``app.dependency_overrides``."""

from collections.abc import AsyncIterator
from typing import Annotated, Any

from absurd_sdk import AsyncAbsurd
from fastapi import Depends, Request
from psycopg import AsyncConnection

from securefabric_api.config import ApiSettings, get_settings
from securefabric_db import AsyncPool
from securefabric_tasks import AbsurdSettings


def get_pool(request: Request) -> AsyncPool:
    pool: AsyncPool = request.app.state.pool
    return pool


def get_absurd_settings(request: Request) -> AbsurdSettings:
    settings: AbsurdSettings = request.app.state.absurd_settings
    return settings


async def get_absurd(
    pool: Annotated[AsyncPool, Depends(get_pool)],
    absurd_settings: Annotated[AbsurdSettings, Depends(get_absurd_settings)],
) -> AsyncIterator[AsyncAbsurd]:
    """Yield an Absurd client bound to a pooled connection for the request's lifetime.

    The client object is cheap; borrowing the connection from the pool (instead of one
    long-lived connection) gives us concurrency and automatic reconnects.
    """
    async with pool.connection() as conn:
        yield AsyncAbsurd(
            conn,
            queue_name=absurd_settings.default_queue,
            default_max_attempts=absurd_settings.default_max_attempts,
        )


async def get_conn(
    pool: Annotated[AsyncPool, Depends(get_pool)],
) -> AsyncIterator[AsyncConnection[Any]]:
    """A pooled (autocommit) connection; domain services open their own transactions."""
    async with pool.connection() as conn:
        yield conn


SettingsDep = Annotated[ApiSettings, Depends(get_settings)]
PoolDep = Annotated[AsyncPool, Depends(get_pool)]
AbsurdDep = Annotated[AsyncAbsurd, Depends(get_absurd)]
ConnDep = Annotated[AsyncConnection[Any], Depends(get_conn)]
