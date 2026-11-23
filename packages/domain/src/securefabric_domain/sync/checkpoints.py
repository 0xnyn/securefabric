"""Checkpoints with optimistic versions (SYNC-04).

Writes are ``update ... where version = expected``; a mismatch means another
slice moved the stream on, and the batch must abort.
"""

import json
from typing import Any
from uuid import UUID

from securefabric_db import Conn, fetch_one


class CheckpointConflict(Exception):
    pass


async def load(
    conn: Conn, connection_id: UUID, stream: str, key: str = "default"
) -> tuple[dict[str, Any] | None, int]:
    row = await fetch_one(
        conn,
        "select value, version from sync.checkpoint where connection_id = %s and stream = %s and key = %s",
        (connection_id, stream, key),
    )
    if row is None:
        return None, 0
    return row["value"], int(row["version"])


async def save(
    conn: Conn,
    environment_id: UUID,
    connection_id: UUID,
    stream: str,
    value: dict[str, Any] | None,
    expected_version: int,
    key: str = "default",
) -> int:
    """Returns the new version. Raises CheckpointConflict on a version mismatch."""
    if expected_version == 0:
        row = await fetch_one(
            conn,
            """insert into sync.checkpoint (connection_id, stream, key, environment_id, value, version)
               values (%s, %s, %s, %s, %s, 1)
               on conflict (connection_id, stream, key) do nothing returning version""",
            (connection_id, stream, key, environment_id, json.dumps(value or {})),
        )
    else:
        row = await fetch_one(
            conn,
            """update sync.checkpoint set value = %s, version = version + 1, updated_at = now()
                where connection_id = %s and stream = %s and key = %s and version = %s returning version""",
            (json.dumps(value or {}), connection_id, stream, key, expected_version),
        )
    if row is None:
        raise CheckpointConflict(
            f"checkpoint {connection_id}/{stream}/{key} moved past version {expected_version}"
        )
    return int(row["version"])


async def clear(conn: Conn, connection_id: UUID, stream: str | None = None) -> None:
    if stream is None:
        await conn.execute("delete from sync.checkpoint where connection_id = %s", (connection_id,))
    else:
        await conn.execute(
            "delete from sync.checkpoint where connection_id = %s and stream = %s",
            (connection_id, stream),
        )
