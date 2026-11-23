"""The transactional outbox (HOOK-04, D7).

An event is a row inserted in the same transaction as the change it describes.
No code path sends a webhook directly: if the transaction commits the event
exists, and if it rolls back it does not. ``sequence`` increases strictly per
connection under the connection's row lock (HOOK-11).
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from securefabric_core.canonical import format_datetime
from securefabric_core.ids import uuid7
from securefabric_db import Conn, fetch_one


def public_event_id(event_id: UUID | str) -> str:
    return f"evt_{UUID(str(event_id)).hex}"


def parse_event_id(value: str) -> UUID:
    return UUID(value.removeprefix("evt_"))


async def emit(
    conn: Conn,
    *,
    environment_id: UUID,
    type: str,
    data: dict[str, Any],
    connection_id: UUID | None = None,
    organization_id: UUID | None = None,
    at: datetime | None = None,
) -> dict[str, Any]:
    sequence = None
    if connection_id is not None:
        row = await fetch_one(
            conn,
            "update control.connection set event_seq = event_seq + 1 where id = %s returning event_seq, "
            "organization_id",
            (connection_id,),
        )
        if row is not None:
            sequence = int(row["event_seq"])
            organization_id = organization_id or row["organization_id"]
    event_id = uuid7()
    created = await fetch_one(conn, "select coalesce(%s::timestamptz, now()) as t", (at,))
    assert created is not None
    envelope = {
        "id": public_event_id(event_id),
        "type": type,
        "created_at": format_datetime(created["t"]),
        "environment_id": str(environment_id),
        "organization_id": str(organization_id) if organization_id else None,
        "connection_id": str(connection_id) if connection_id else None,
        "sequence": sequence,
        "data": data,
    }
    await conn.execute(
        """insert into events.outbox_event (id, environment_id, organization_id, connection_id, sequence, type,
                                            payload, created_at)
           values (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            event_id,
            environment_id,
            organization_id,
            connection_id,
            sequence,
            type,
            json.dumps(envelope, default=str),
            created["t"],
        ),
    )
    await conn.execute("select pg_notify('sf_outbox', %s)", (str(environment_id),))
    return envelope
