"""Connection health (docs/plan/03-tenancy-connections-vault.md, section 7; CON-12).

Health is orthogonal to state. Every stream run ends with exactly one code; the
connection's health is the worst code across the latest run of each enabled
stream (fixed severity order). A ``NOT_ENABLED`` grant never makes a connection
unhealthy: it appears in ``details`` with ``reason: feature_not_enabled``.

A change writes a ``connection_health_event`` row and a
``connection.health.changed`` outbox event in the same transaction (HOOK-01).
"""

import json
from typing import Any
from uuid import UUID

from securefabric_db import Conn, fetch_all, fetch_one
from securefabric_domain.events.outbox import emit
from securefabric_schema import HealthCode


async def compute(
    conn: Conn,
    connection_id: UUID,
    *,
    override: HealthCode | None = None,
    override_detail: str | None = None,
) -> tuple[HealthCode, list[dict[str, Any]], str]:
    c = await fetch_one(
        conn,
        """select c.*, i.enabled_streams from control.connection c
             join control.integration i on i.id = c.integration_id where c.id = %s""",
        (connection_id,),
    )
    assert c is not None
    enabled = list(c["enabled_streams"] or [])
    grants = {
        g["stream"]: g
        for g in await fetch_all(
            conn,
            "select * from control.connection_grant where connection_id = %s",
            (connection_id,),
        )
    }
    latest = {
        r["stream"]: r
        for r in await fetch_all(
            conn,
            """select distinct on (stream) stream, state, health_code, finished_at from sync.stream_run
                where connection_id = %s and mode <> 'targeted'
                  and state in ('SUCCEEDED', 'FAILED', 'CANCELLED', 'EXPIRED')
                order by stream, finished_at desc nulls last""",
            (connection_id,),
        )
    }
    details: list[dict[str, Any]] = []
    codes: list[HealthCode] = []
    for stream in enabled:
        g = grants.get(stream)
        if g and g["status"] == "NOT_ENABLED":
            details.append(
                {
                    "data_export_type": stream,
                    "endpoint": g["endpoint"],
                    "reason": "feature_not_enabled",
                }
            )
            continue
        if g and g["status"] == "UNAUTHORIZED":
            codes.append(HealthCode.UNAUTHORIZED)
            details.append(
                {
                    "data_export_type": stream,
                    "endpoint": g["endpoint"],
                    "reason": "permission_missing",
                }
            )
            continue
        if g and g["status"] == "UNSUPPORTED":
            details.append(
                {"data_export_type": stream, "endpoint": g["endpoint"], "reason": "unsupported"}
            )
            continue
        run = latest.get(stream)
        if run is None:
            codes.append(HealthCode.INITIALIZING)
        elif run["state"] == "SUCCEEDED":
            codes.append(HealthCode.HEALTHY)
        elif run["state"] == "FAILED" and run["health_code"]:
            code = HealthCode(run["health_code"])
            codes.append(code)
            if code is not HealthCode.HEALTHY:
                details.append(
                    {"data_export_type": stream, "endpoint": None, "reason": code.value.lower()}
                )
        else:
            codes.append(
                HealthCode.HEALTHY if run["state"] == "CANCELLED" else HealthCode.INITIALIZING
            )
    revoked = (c["connection_config"] or {}).get("_revoked")
    if revoked:
        codes.append(HealthCode.UNAUTHORIZED)
        if override is None:
            override, override_detail = HealthCode.UNAUTHORIZED, revoked.get("reason")
    if override is not None:
        codes.append(override)
    code = max(codes, key=lambda h: h.severity) if codes else HealthCode.HEALTHY
    description = override_detail if override is not None and override_detail else code.description
    return code, details, description


async def recompute(
    conn: Conn,
    connection_id: UUID,
    *,
    job_id: UUID | None = None,
    override: HealthCode | None = None,
    override_detail: str | None = None,
) -> tuple[HealthCode, bool]:
    """Recompute and persist. Returns (code, changed)."""
    c = await fetch_one(
        conn,
        "select environment_id, organization_id, health_code, health_details, state "
        "from control.connection where id = %s for update",
        (connection_id,),
    )
    if c is None or c["state"] in ("DELETED", "HARD_DELETED"):
        return HealthCode.HEALTHY, False
    code, details, description = await compute(
        conn, connection_id, override=override, override_detail=override_detail
    )
    if c["health_code"] == code.value and c["health_details"] == details:
        return code, False
    await conn.execute(
        """update control.connection set health_code = %s, health_status = %s, resolution_owner = %s,
                  health_details = %s, health_description = %s, health_changed_at = now(), updated_at = now()
            where id = %s""",
        (
            code.value,
            code.status.value,
            code.owner.value if code.owner else None,
            json.dumps(details),
            description,
            connection_id,
        ),
    )
    if c["health_code"] != code.value:
        await conn.execute(
            """insert into control.connection_health_event (connection_id, environment_id, from_code, to_code,
              details, job_id)
               values (%s, %s, %s, %s, %s, %s)""",
            (
                connection_id,
                c["environment_id"],
                c["health_code"],
                code.value,
                json.dumps(details),
                job_id,
            ),
        )
        await emit(
            conn,
            environment_id=c["environment_id"],
            connection_id=connection_id,
            organization_id=c["organization_id"],
            type="connection.health.changed",
            data={
                "previous": c["health_code"],
                "health": health_object(code, details, description),
            },
        )
    return code, True


def health_object(
    code: HealthCode, details: list[dict[str, Any]], description: str | None = None
) -> dict[str, Any]:
    """The Leen-shaped health object (CON-12)."""
    return {
        "name": code.value,
        "status": code.status.value,
        "description": description or code.description,
        "resolution_owner": code.owner.value if code.owner else None,
        "details": details or None,
    }
