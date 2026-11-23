"""Customer-visible operation logs (OBS-01): ``obs.operation`` + ``obs.operation_event``.

One operation per logical action (a stream run, a verification, a webhook...).
Lines are buffered and flushed in their own transaction; bodies and headers are
never stored, and every message passes redaction (SEC-07).
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from securefabric_core.ids import uuid7
from securefabric_core.redact import redact, redact_text
from securefabric_db import AsyncPool, tenant_tx

MAX_BUFFER = 200


class OperationLog:
    def __init__(self, pool: AsyncPool, *, environment_id: UUID, operation_id: UUID) -> None:
        self._pool = pool
        self._env = environment_id
        self.operation_id = operation_id
        self._buffer: list[tuple[Any, ...]] = []
        self.http_calls = 0
        self.errors = 0

    def log(self, level: str, message: str, **fields: Any) -> None:
        if level == "error":
            self.errors += 1
        text = redact_text(message)
        if fields:
            text = f"{text} {json.dumps(redact(fields), default=str, sort_keys=True)}"
        self._buffer.append(
            (
                level if level in ("debug", "info", "warning", "error") else "info",
                "log",
                text[:4000],
                None,
            )
        )

    def http(self, entry: dict[str, Any]) -> None:
        self.http_calls += 1
        status = entry.get("status")
        level = "info" if status and status < 400 else "warning"
        msg = f"{entry.get('method')} {entry.get('path')} -> {status or entry.get('error')}"
        self._buffer.append((level, "http", msg, json.dumps(redact(entry), default=str)))

    async def flush(self) -> None:
        if not self._buffer:
            return
        rows, self._buffer = self._buffer, []
        async with tenant_tx(self._pool, self._env) as conn, conn.cursor() as cur:
            await cur.executemany(
                """insert into obs.operation_event (operation_id, environment_id, level, kind, message, http)
                       values (%s, %s, %s, %s, %s, %s)""",
                [
                    (self.operation_id, self._env, lvl, kind, msg, http)
                    for lvl, kind, msg, http in rows
                ],
            )

    async def maybe_flush(self) -> None:
        if len(self._buffer) >= MAX_BUFFER:
            await self.flush()


async def start_operation(
    pool: AsyncPool,
    *,
    environment_id: UUID,
    kind: str,
    action: str,
    connection_id: UUID | None = None,
    organization_id: UUID | None = None,
    job_id: UUID | None = None,
    stream_run_id: UUID | None = None,
    request_id: str | None = None,
    started_at: datetime | None = None,
) -> OperationLog:
    op_id = uuid7()
    async with tenant_tx(pool, environment_id) as conn:
        await conn.execute(
            """insert into obs.operation (id, environment_id, connection_id, organization_id, kind, action, status,
                                          job_id, stream_run_id, request_id, started_at)
               values (%s, %s, %s, %s, %s, %s, 'running', %s, %s, %s, coalesce(%s, now()))""",
            (
                op_id,
                environment_id,
                connection_id,
                organization_id,
                kind,
                action,
                job_id,
                stream_run_id,
                request_id,
                started_at,
            ),
        )
    return OperationLog(pool, environment_id=environment_id, operation_id=op_id)


async def finish_operation(
    pool: AsyncPool, log: OperationLog, *, status: str, summary: dict[str, Any]
) -> None:
    await log.flush()
    async with tenant_tx(pool, log._env) as conn:
        await conn.execute(
            """update obs.operation set status = %s, summary = %s,
                      duration_ms = (extract(epoch from (clock_timestamp() - started_at)) * 1000)::int
                where id = %s""",
            (status, json.dumps(redact(summary), default=str), log.operation_id),
        )
