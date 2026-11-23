"""The action plane: write-back (docs/plan/07-public-api-and-events.md, section 7; ACT-02, ACT-03).

``POST /v1/vulnerability_findings/{id}/actions`` with ``{action: "set_state",
state, reason, comment}``. Requires ``actions:write``, an integration with
write-back enabled, a connector that declares the action, and an
``Idempotency-Key`` (a repeat returns the first result). It runs as a control
task; on success the record is marked dirty and re-fetched, so our state
reflects what the vendor recorded, not what we asked for, and
``action.completed`` is emitted.
"""

import asyncio
import json
from typing import Any
from uuid import UUID

from securefabric_cdk.errors import ConnectorError
from securefabric_cdk.types import Action
from securefabric_core import BadRequestError, NotFoundError, ValidationFailedError, get_logger
from securefabric_db import fetch_one, tenant_tx
from securefabric_domain.data_api import resolve_scope
from securefabric_domain.events.outbox import emit
from securefabric_domain.runtime import Platform
from securefabric_domain.tenancy import Principal, audit
from securefabric_tasks.spec import spawn_sql

log = get_logger(__name__)

CANONICAL_REASONS = ("false_positive", "accepted_risk", "test_code", "revoked")
STATES = ("OPEN", "IGNORED", "CLOSED")


def _out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        k: row[k]
        for k in (
            "id",
            "connection_id",
            "finding_id",
            "name",
            "params",
            "status",
            "vendor_response",
            "message",
            "created_at",
            "finished_at",
        )
    }


async def request_action(
    platform: Platform,
    principal: Principal,
    finding_id: UUID,
    body: dict[str, Any],
    *,
    connection_header: str | None,
    organization_header: str | None,
    idempotency_key: str | None,
) -> dict[str, Any]:
    principal.require("actions:write")
    if not idempotency_key:
        raise BadRequestError(
            "Actions require an Idempotency-Key header.", code="idempotency_key_required"
        )
    action = body.get("action")
    if action != "set_state":
        raise ValidationFailedError(
            "action must be set_state",
            code="invalid_action",
            errors=[{"field": "action", "message": "set_state"}],
        )
    state = str(body.get("state", "")).upper()
    reason = body.get("reason")
    if state not in STATES:
        raise ValidationFailedError(
            f"state must be one of {STATES}",
            code="invalid_action",
            errors=[{"field": "state", "message": "OPEN | IGNORED | CLOSED"}],
        )
    if state != "OPEN" and reason not in CANONICAL_REASONS:
        raise ValidationFailedError(
            f"reason must be one of {CANONICAL_REASONS}",
            code="invalid_action",
            errors=[{"field": "reason", "message": "required for IGNORED and CLOSED"}],
        )
    async with tenant_tx(platform.pool, principal.env) as conn:
        scope = await resolve_scope(
            conn,
            connection_header=connection_header,
            organization_header=organization_header,
            connection_filter=None,
        )
        f = await fetch_one(
            conn,
            "select id, connection_id, natural_key, vendor_id, stream, state from data.vulnerability_finding "
            "where id = %s and connection_id = any(%s) and deleted_at is null",
            (finding_id, scope.connection_ids),
        )
        if f is None:
            raise NotFoundError("Finding not found", code="finding_not_found")
        c = await fetch_one(
            conn,
            """select c.*, i.write_back_enabled from control.connection c
                                       join control.integration i on i.id = c.integration_id where c.id = %s""",
            (f["connection_id"],),
        )
        assert c is not None
        manifest = platform.registry.manifest(c["connector_id"])
        spec = manifest.action("finding.set_state")
        if spec is None:
            raise ValidationFailedError(
                f"{manifest.display_name} does not support write-back.", code="action_unsupported"
            )
        if not c["write_back_enabled"] and spec.requires_permission_tier == "read_write":
            raise ValidationFailedError(
                "Write-back is not enabled on this integration.", code="write_back_disabled"
            )
        if c["state"] != "ACTIVE":
            raise ValidationFailedError(
                f"The connection is {c['state']}.", code="connection_not_active"
            )
        expressible = _expressible(platform, c["connector_id"], f["natural_key"], state, reason)
        if not expressible:
            allowed = [
                f"{st}:{r}" if st != "OPEN" else "OPEN"
                for st in STATES
                for r in ([None] if st == "OPEN" else spec.reasons)
                if _expressible(platform, c["connector_id"], f["natural_key"], st, r)
            ]
            raise ValidationFailedError(
                f"{manifest.display_name} cannot record {state} with reason {reason!r}. Supported: {allowed}",
                code="reason_unsupported",
                errors=[{"field": "reason", "message": f"supported: {allowed}"}],
            )
        params = {
            "state": state,
            "reason": reason if state != "OPEN" else None,
            "comment": body.get("comment"),
        }
        row = await fetch_one(
            conn,
            """insert into control.action (environment_id, connection_id, finding_id, name, params, requested_by,
              request_id)
               values (%s, %s, %s, 'finding.set_state', %s, %s, %s) returning *""",
            (
                principal.env,
                c["id"],
                finding_id,
                json.dumps(params),
                f"{principal.kind}:{principal.actor_id}",
                principal.request_id,
            ),
        )
        assert row is not None
        await spawn_sql(
            conn,
            queue="control",
            task_name="action.perform",
            params={"action_id": str(row["id"]), "environment_id": str(principal.env)},
            idempotency_key=f"action:{row['id']}",
            max_attempts=1,
        )
        await audit(
            conn,
            principal,
            "action.requested",
            target_kind="vulnerability_finding",
            target_id=finding_id,
            detail={"action_id": str(row["id"]), **params},
        )
    return _out(row)


def _expressible(
    platform: Platform, connector_id: str, natural_key: str, state: str, reason: str | None
) -> bool:
    spec = platform.registry.manifest(connector_id).action("finding.set_state")
    if spec is None or (state != "OPEN" and reason not in spec.reasons):
        return False
    if connector_id == "GITHUB":
        from securefabric_connectors.github import mapping

        family = natural_key.split(":", 1)[0]
        return (state, reason if state != "OPEN" else None) in mapping.WRITE_BACK.get(family, {})
    if connector_id == "SANDBOX":
        from securefabric_connectors.sandbox import mapping as sm

        return (state, reason if state == "IGNORED" else None) in sm.SET_STATE
    return True


async def get_action(
    platform: Platform, principal: Principal, action_id: UUID, *, wait_s: float = 0
) -> dict[str, Any]:
    principal.require("provisioning:read")
    deadline = asyncio.get_running_loop().time() + min(max(wait_s, 0), 30)
    while True:
        async with tenant_tx(platform.pool, principal.env) as conn:
            row = await fetch_one(conn, "select * from control.action where id = %s", (action_id,))
        if row is None:
            raise NotFoundError("Action not found", code="action_not_found")
        if row["status"] != "PENDING" or asyncio.get_running_loop().time() >= deadline:
            return _out(row)
        await asyncio.sleep(0.25)


async def perform_action(
    platform: Platform, environment_id: UUID, action_id: UUID
) -> dict[str, Any]:
    """Control worker: perform against the vendor, then re-fetch what the vendor recorded."""
    from securefabric_domain.sync.bundle import build_context, load_bundle
    from securefabric_domain.sync.oplog import finish_operation, start_operation

    async with tenant_tx(platform.pool, environment_id) as conn:
        a = await fetch_one(conn, "select * from control.action where id = %s", (action_id,))
        if a is None or a["status"] != "PENDING":
            return {"ok": True, "detail": {"skipped": True}}
        f = await fetch_one(
            conn,
            "select * from data.vulnerability_finding where connection_id = %s and id = %s",
            (a["connection_id"], a["finding_id"]),
        )
        bundle = await load_bundle(platform, conn, a["connection_id"])
    op = await start_operation(
        platform.pool,
        environment_id=environment_id,
        kind="action",
        action=a["name"],
        connection_id=a["connection_id"],
        organization_id=bundle.connection["organization_id"],
        request_id=a["request_id"],
    )
    ctx = await build_context(
        platform,
        bundle,
        stream=f["stream"] if f else None,
        op_log=op,
        capture=None,
        clock=platform.clock,
        interactive=True,
    )
    status, message, response, refetch = "FAILED", None, None, []
    try:
        if f is None:
            raise NotFoundError("the finding no longer exists")
        result = await bundle.connector.perform(
            ctx,
            Action(
                name=a["name"],
                params=a["params"],
                record={
                    "natural_key": f["natural_key"],
                    "vendor_id": f["vendor_id"],
                    "stream": f["stream"],
                },
            ),
        )
        status, message, response, refetch = (
            result.status,
            result.message,
            result.vendor_response,
            result.refetch,
        )
    except (ConnectorError, NotFoundError) as exc:
        message = getattr(exc, "message", str(exc))
    finally:
        await ctx.http.aclose()
    async with tenant_tx(platform.pool, environment_id) as conn:
        await conn.execute(
            "update control.action set status = %s, message = %s, vendor_response = %s, finished_at = now() "
            "where id = %s",
            (status, message, json.dumps(response), action_id),
        )
        for d in refetch:
            await conn.execute(
                """insert into sync.dirty_record (connection_id, stream, vendor_key, environment_id, reason)
                   values (%s, %s, %s, %s, %s) on conflict (connection_id, stream, vendor_key) do nothing""",
                (a["connection_id"], d.stream, d.key, environment_id, d.reason),
            )
        await emit(
            conn,
            environment_id=environment_id,
            connection_id=a["connection_id"],
            type="action.completed" if status == "SUCCEEDED" else "action.failed",
            data={
                "action_id": str(action_id),
                "finding_id": str(a["finding_id"]),
                "params": a["params"],
                "status": status,
                "message": message,
            },
        )
        await conn.execute("select pg_notify('sf_admit', %s)", (str(action_id),))
    await finish_operation(
        platform.pool,
        op,
        status="success" if status == "SUCCEEDED" else "failed",
        summary={"action_id": str(action_id), "status": status, "message": message},
    )
    return {"ok": status == "SUCCEEDED", "detail": {"status": status, "message": message}}
