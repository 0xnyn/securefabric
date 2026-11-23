"""Inbound vendor webhooks (docs/plan/06-github-connector.md, section 8; PD-11).

1. API: verify the signature (constant time) with the vendor app's webhook secret,
   held under the ingress key the API has. Unsigned deliveries are never accepted.
2. API: insert into ``sync.ingress_delivery`` keyed by (vendor app, delivery id):
   a duplicate is acknowledged and dropped (redelivery is safe). Return 202.
3. Control worker: resolve the tenant reference to connections, ask the connector
   what the delivery means (a pure function), and apply the effects.

Payloads are signals, never data: a dirty alert is re-fetched from the vendor.
"""

import json
from typing import Any
from uuid import UUID

from securefabric_cdk.types import (
    ConnectionRestored,
    ConnectionRevoked,
    Ignore,
    IngressDelivery,
    MarkDirty,
    ReprobeGrants,
    TriggerStream,
    UpdateConfig,
)
from securefabric_core import NotFoundError, UnauthenticatedError, get_logger
from securefabric_core.crypto import constant_time_equals, hmac_sha256_hex
from securefabric_db import fetch_all, fetch_one, system_tx, tenant_tx
from securefabric_domain.events.outbox import emit
from securefabric_domain.runtime import Platform
from securefabric_domain.sync import health, jobs
from securefabric_domain.sync.bundle import budget_key_for
from securefabric_schema import HealthCode, Mode
from securefabric_tasks.spec import spawn_sql

log = get_logger(__name__)


def _dig(payload: dict[str, Any], path: str) -> Any:
    cur: Any = payload
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


_SIGNATURE_FAILURES: dict[str, list[float]] = {}


async def _candidate_apps(platform: Platform, connector: str, ref: str) -> list[dict[str, Any]]:
    """The vendor app(s) a delivery URL names. ``default`` means the platform-owned apps.
    An exact lookup through a narrow SECURITY DEFINER function: the API never browses
    other tenants' apps."""
    async with platform.pool.connection() as conn:
        return await fetch_all(
            conn,
            "select * from control.vendor_app_ingress(%s, %s)",
            (connector.upper(), ref.lower()),
        )


async def receive(
    platform: Platform, connector: str, vendor_app_ref: str, headers: dict[str, str], body: bytes
) -> dict[str, Any]:
    """The API side. Returns ``{"status": "accepted"|"duplicate", "id": ...}`` or raises 401/404."""
    manifest = platform.registry.manifest(connector.upper())
    spec = manifest.webhooks
    if spec is None or platform.ingress is None:
        raise NotFoundError("This connector does not accept webhooks", code="ingress_not_found")
    signature = headers.get(spec.signature_header, "")
    if not signature:
        raise UnauthenticatedError("Unsigned delivery", code="signature_missing")
    apps = await _candidate_apps(platform, connector, vendor_app_ref)
    if not apps:
        raise NotFoundError("Unknown vendor app", code="ingress_not_found")
    matched = None
    for app in apps:
        if not app["ingress_secret_enc"]:
            continue
        secret = platform.ingress.decrypt(bytes(app["ingress_secret_enc"]), bound_to=str(app["id"]))
        expected = spec.signature_prefix + hmac_sha256_hex(secret, body)
        if constant_time_equals(expected, signature):
            matched = app
            break
    if matched is None:
        import time

        window = [
            t for t in _SIGNATURE_FAILURES.get(vendor_app_ref, []) if time.time() - t < 60
        ] + [time.time()]
        _SIGNATURE_FAILURES[vendor_app_ref] = window
        log.warning("ingress_signature_rejected", connector=connector, vendor_app=vendor_app_ref)
        if len(window) >= 10:
            from securefabric_domain.sync.scheduler import raise_alert

            async with platform.pool.connection() as conn:
                await raise_alert(
                    conn,
                    "ingress_signature_failures",
                    f"{connector}/{vendor_app_ref}",
                    {"failures_last_minute": len(window)},
                    severity="ticket",
                )
        raise UnauthenticatedError("Invalid signature", code="signature_invalid")
    payload = json.loads(body or b"{}")
    delivery_id = headers.get(spec.delivery_id_header) or hmac_sha256_hex("ingress", body)
    event = headers.get(spec.event_header, "unknown")
    action = _dig(payload, spec.action_path)
    ref = _dig(payload, spec.tenant_ref_path)
    async with platform.pool.connection() as conn, conn.transaction():
        row = await fetch_one(
            conn,
            """insert into sync.ingress_delivery (vendor_app_id, connector_id, delivery_id, event, action,
              vendor_tenant_ref, payload)
               values (%s, %s, %s, %s, %s, %s, %s) on conflict (vendor_app_id, delivery_id) do nothing returning
                 id""",
            (
                matched["id"],
                manifest.id,
                delivery_id,
                event,
                action if isinstance(action, str) else None,
                str(ref) if ref is not None else None,
                json.dumps(payload),
            ),
        )
        if row is None:
            return {"status": "duplicate", "delivery_id": delivery_id}
        await spawn_sql(
            conn,
            queue="control",
            task_name="ingress.process",
            params={"delivery_row_id": str(row["id"])},
            idempotency_key=f"ingress:{row['id']}",
            max_attempts=5,
        )
    return {"status": "accepted", "id": str(row["id"]), "delivery_id": delivery_id}


async def process_delivery(platform: Platform, row_id: UUID) -> dict[str, Any]:
    """Control worker: route and apply effects (cross-tenant routing on sf_system)."""
    async with system_tx(platform.sys_pool) as conn:
        d = await fetch_one(
            conn, "select * from sync.ingress_delivery where id = %s for update", (row_id,)
        )
        if d is None or d["status"] != "RECEIVED":
            return {"ok": True, "detail": {"skipped": True}}
        if d["vendor_tenant_ref"] is None:
            await conn.execute(
                "update sync.ingress_delivery set status = 'IGNORED', detail = 'no tenant reference', "
                "processed_at = now() where id = %s",
                (row_id,),
            )
            return {"ok": True, "detail": {"routed": 0}}
        # Connections on this installation, through integrations using this vendor app
        # (or the platform default when the integration names none).
        connections = await fetch_all(
            conn,
            """select c.* from control.connection c join control.integration i on i.id = c.integration_id
                where c.vendor_tenant_ref = %s and c.connector_id = %s and c.deleted_at is null
                  and (i.vendor_app_id = %s or (i.vendor_app_id is null and exists (
                       select 1 from control.vendor_app a where a.id = %s and a.environment_id is null)))""",
            (d["vendor_tenant_ref"], d["connector_id"], d["vendor_app_id"], d["vendor_app_id"]),
        )
    connector = platform.registry.get(d["connector_id"])
    delivery = IngressDelivery(
        delivery_id=d["delivery_id"],
        event=d["event"],
        action=d["action"],
        payload=d["payload"],
        vendor_tenant_ref=d["vendor_tenant_ref"],
    )
    applied: list[str] = []
    for c in connections:
        effects = connector.handle_webhook(
            delivery, config=c["connection_config"] or {}, options=c["options"] or {}
        )
        async with tenant_tx(platform.pool, c["environment_id"]) as conn:
            for effect in effects:
                applied.append(type(effect).__name__)
                await _apply(platform, conn, c, effect)
            await conn.execute(
                """insert into obs.operation (environment_id, connection_id, organization_id, kind, action, status,
                  summary)
                   values (%s, %s, %s, 'webhook_in', %s, 'success', %s)""",
                (
                    c["environment_id"],
                    c["id"],
                    c["organization_id"],
                    f"{d['event']}.{d['action'] or ''}".rstrip("."),
                    json.dumps(
                        {
                            "delivery_id": d["delivery_id"],
                            "effects": [type(e).__name__ for e in effects],
                        }
                    ),
                ),
            )
            await conn.execute("select pg_notify('sf_admit', %s)", (str(c["id"]),))
    status = "ROUTED" if connections and any(a != "Ignore" for a in applied) else "IGNORED"
    async with system_tx(platform.sys_pool) as conn:
        await conn.execute(
            "update sync.ingress_delivery set status = %s, processed_at = now(), detail = %s where id = %s",
            (
                status,
                f"{len(connections)} connection(s): {', '.join(sorted(set(applied))) or 'none'}",
                row_id,
            ),
        )
    return {"ok": True, "detail": {"routed": len(connections), "effects": applied}}


async def _apply(platform: Platform, conn: Any, c: dict[str, Any], effect: Any) -> None:
    env, cid = c["environment_id"], c["id"]
    if isinstance(effect, Ignore):
        return
    if isinstance(effect, MarkDirty):
        if c["state"] != "ACTIVE":
            return
        await conn.execute(
            """insert into sync.dirty_record (connection_id, stream, vendor_key, environment_id, reason)
               values (%s, %s, %s, %s, %s) on conflict (connection_id, stream, vendor_key) do update
               set enqueued_at = excluded.enqueued_at, reason = excluded.reason""",
            (cid, effect.stream, effect.key, env, effect.reason[:200]),
        )
        return
    if isinstance(effect, TriggerStream):
        if c["state"] != "ACTIVE":
            return
        manifest = platform.registry.manifest(c["connector_id"])
        mode = (
            Mode.FULL
            if effect.full
            else await jobs.mode_for(
                conn, manifest, cid, effect.stream, force_full=False, now=platform.clock.now()
            )
        )
        await jobs.create_job(
            conn,
            c,
            job_type="WEBHOOK",
            runs=[(effect.stream, mode)],
            priority=jobs.PRIORITY_INTERACTIVE,
            budget_key=await budget_key_for(platform, conn, cid),
            requested_by="webhook",
            now=platform.clock.now(),
        )
        return
    if isinstance(effect, ConnectionRevoked):
        # Health UNAUTHORIZED (owner CUSTOMER), schedules paused, data stays readable.
        await conn.execute(
            "update control.connection set connection_config = connection_config || %s, updated_at = now() where id "
            "= %s",
            (
                json.dumps({"_revoked": {"reason": effect.reason, "suspended": effect.suspended}}),
                cid,
            ),
        )
        await jobs.set_schedules_state(conn, cid, "PAUSED")
        _code, changed = await health.recompute(
            conn, cid, override=HealthCode.UNAUTHORIZED, override_detail=effect.reason
        )
        if changed:
            await emit(
                conn,
                environment_id=env,
                connection_id=cid,
                type="connection.sync.unauthorized",
                data={
                    "vendor": c["connector_id"],
                    "error": "UNAUTHORIZED",
                    "description": effect.reason,
                },
            )
        return
    if isinstance(effect, ConnectionRestored):
        await conn.execute(
            "update control.connection set connection_config = connection_config - '_revoked' where id = %s",
            (cid,),
        )
        await spawn_sql(
            conn,
            queue="control",
            task_name="connection.verify",
            params={
                "connection_id": str(cid),
                "environment_id": str(env),
                "reason": "restore",
                "staged": False,
            },
        )
        return
    if isinstance(effect, ReprobeGrants):
        await spawn_sql(
            conn,
            queue="control",
            task_name="connection.verify",
            params={
                "connection_id": str(cid),
                "environment_id": str(env),
                "reason": "reprobe",
                "staged": False,
            },
        )
        return
    if isinstance(effect, UpdateConfig):
        await conn.execute(
            "update control.connection set connection_config = connection_config || %s, updated_at = now() "
            "where id = %s",
            (json.dumps(effect.updates), cid),
        )
        return
