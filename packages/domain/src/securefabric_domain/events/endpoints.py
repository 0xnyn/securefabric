"""Webhook endpoints, delivery log, replay and the pull feed (HOOK-02/06/07, part 7 section 9)."""

import json
from datetime import timedelta
from typing import Any
from uuid import UUID

from psycopg import errors as pg_errors

from securefabric_cdk.egress import check_url
from securefabric_cdk.errors import EgressDenied
from securefabric_core import ConflictError, NotFoundError, ValidationFailedError
from securefabric_core.crypto import random_token
from securefabric_db import Conn, fetch_all, fetch_one, fetch_required, tenant_tx
from securefabric_domain.events.outbox import parse_event_id, public_event_id
from securefabric_domain.runtime import Platform
from securefabric_domain.tenancy import Principal, audit
from securefabric_domain.vault import seal_for
from securefabric_schema import RESERVED_EVENT_TYPES, EventType
from securefabric_tasks.spec import spawn_sql

MAX_ENDPOINTS = 5
ROTATION_OVERLAP = timedelta(hours=24)
EVENT_TYPES = sorted(e.value for e in EventType)


def _out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        k: row[k]
        for k in (
            "id",
            "url",
            "description",
            "event_types",
            "enabled",
            "disabled_reason",
            "failing_since",
            "created_at",
            "secret_hint",
            "previous_secret_expires_at",
        )
    }


async def _validate(platform: Platform, url: str, event_types: list[str]) -> None:
    if len(url) > 2048:
        raise ValidationFailedError("url is limited to 2,048 characters", code="invalid_url")
    try:
        await check_url(
            url, allow_private=platform.settings.egress_allow_private, require_https=True
        )
    except EgressDenied as exc:
        raise ValidationFailedError(
            f"url rejected: {exc.message}",
            code="invalid_url",
            errors=[{"field": "url", "message": exc.message}],
        ) from exc
    unknown = [t for t in event_types if t not in EVENT_TYPES and t not in RESERVED_EVENT_TYPES]
    if unknown:
        raise ValidationFailedError(
            f"Unknown event types: {unknown}",
            code="invalid_event_types",
            errors=[{"field": "event_types", "message": f"unknown: {unknown}"}],
        )


def new_secret() -> str:
    return "whsec_" + random_token(32)


async def create_endpoint(
    platform: Platform,
    principal: Principal,
    *,
    url: str,
    description: str | None,
    event_types: list[str],
    enabled: bool = True,
) -> dict[str, Any]:
    principal.require("webhooks:manage")
    await _validate(platform, url, event_types)
    secret = new_secret()
    from securefabric_core.ids import uuid7

    eid = uuid7()
    async with tenant_tx(platform.pool, principal.env) as conn:
        sealed, version = await seal_for(
            conn, principal.env, connection_id=eid, purpose="webhook_secret", payload=secret
        )
        try:
            row = await fetch_one(
                conn,
                """insert into events.webhook_endpoint (id, environment_id, url, description, event_types,
                  secret_sealed,
                       secret_key_version, secret_hint, enabled) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                         returning *""",
                (
                    eid,
                    principal.env,
                    url,
                    description,
                    event_types,
                    sealed,
                    version,
                    secret[-4:],
                    enabled,
                ),
            )
        except pg_errors.CheckViolation as exc:
            raise ConflictError(
                f"At most {MAX_ENDPOINTS} webhook endpoints per environment.", code="endpoint_limit"
            ) from exc
        assert row is not None
        await audit(
            conn,
            principal,
            "webhook_endpoint.created",
            target_kind="webhook_endpoint",
            target_id=eid,
        )
    return {**_out(row), "secret": secret}


async def list_endpoints(platform: Platform, principal: Principal) -> list[dict[str, Any]]:
    principal.require("webhooks:manage")
    async with tenant_tx(platform.pool, principal.env) as conn:
        return [
            _out(r)
            for r in await fetch_all(
                conn,
                "select * from events.webhook_endpoint where deleted_at is null order by created_at",
            )
        ]


async def _get(conn: Conn, endpoint_id: UUID) -> dict[str, Any]:
    row = await fetch_one(
        conn,
        "select * from events.webhook_endpoint where id = %s and deleted_at is null",
        (endpoint_id,),
    )
    if row is None:
        raise NotFoundError("Webhook endpoint not found", code="webhook_endpoint_not_found")
    return row


async def get_endpoint(
    platform: Platform, principal: Principal, endpoint_id: UUID
) -> dict[str, Any]:
    principal.require("webhooks:manage")
    async with tenant_tx(platform.pool, principal.env) as conn:
        return _out(await _get(conn, endpoint_id))


async def update_endpoint(
    platform: Platform, principal: Principal, endpoint_id: UUID, changes: dict[str, Any]
) -> dict[str, Any]:
    principal.require("webhooks:manage")
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await _get(conn, endpoint_id)
        url = changes.get("url") or row["url"]
        types = (
            changes["event_types"] if changes.get("event_types") is not None else row["event_types"]
        )
        await _validate(platform, url, types)
        enabled = changes["enabled"] if changes.get("enabled") is not None else row["enabled"]
        row = await fetch_required(
            conn,
            """update events.webhook_endpoint set url = %s, event_types = %s, description = coalesce(%s, description),
                      enabled = %s, disabled_reason = case when %s then null else disabled_reason end,
                      failing_since = case when %s and not enabled then null else failing_since end
                where id = %s returning *""",
            (url, types, changes.get("description"), enabled, enabled, enabled, endpoint_id),
        )
        assert row is not None
        await audit(
            conn,
            principal,
            "webhook_endpoint.updated",
            target_kind="webhook_endpoint",
            target_id=endpoint_id,
            detail={"fields": sorted(changes)},
        )
    return _out(row)


async def delete_endpoint(platform: Platform, principal: Principal, endpoint_id: UUID) -> None:
    principal.require("webhooks:manage")
    async with tenant_tx(platform.pool, principal.env) as conn:
        await _get(conn, endpoint_id)
        await conn.execute(
            "update events.webhook_endpoint set deleted_at = now(), enabled = false where id = %s",
            (endpoint_id,),
        )
        await audit(
            conn,
            principal,
            "webhook_endpoint.deleted",
            target_kind="webhook_endpoint",
            target_id=endpoint_id,
        )


async def rotate_secret(
    platform: Platform, principal: Principal, endpoint_id: UUID
) -> dict[str, Any]:
    """For 24 hours after a rotation both secrets sign and both signatures are sent (HOOK-03)."""
    principal.require("webhooks:manage")
    secret = new_secret()
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await _get(conn, endpoint_id)
        sealed, version = await seal_for(
            conn, principal.env, connection_id=endpoint_id, purpose="webhook_secret", payload=secret
        )
        row = await fetch_required(
            conn,
            """update events.webhook_endpoint set previous_secret_sealed = secret_sealed,
                      previous_secret_expires_at = %s, secret_sealed = %s, secret_key_version = %s,
                      secret_hint = %s where id = %s returning *""",
            (platform.clock.now() + ROTATION_OVERLAP, sealed, version, secret[-4:], endpoint_id),
        )
        assert row is not None
        await audit(
            conn,
            principal,
            "webhook_endpoint.secret_rotated",
            target_kind="webhook_endpoint",
            target_id=endpoint_id,
        )
    return {**_out(row), "secret": secret}


async def ping(platform: Platform, principal: Principal, endpoint_id: UUID) -> dict[str, Any]:
    """A ``webhook.ping`` event delivered to this endpoint only."""
    principal.require("webhooks:manage")
    from securefabric_domain.events.outbox import emit

    async with tenant_tx(platform.pool, principal.env) as conn:
        await _get(conn, endpoint_id)
        env = await emit(
            conn,
            environment_id=principal.env,
            type="webhook.ping",
            data={"endpoint_id": str(endpoint_id), "message": "Hello from SecureFabric"},
        )
        event_id = parse_event_id(env["id"])
        # Dispatch to this endpoint now, and mark the event dispatched so it is not fanned out.
        d = await fetch_one(
            conn,
            """insert into events.webhook_delivery (environment_id, event_id, endpoint_id, event_type,
              next_attempt_at)
               values (%s, %s, %s, 'webhook.ping', now()) returning id""",
            (principal.env, event_id, endpoint_id),
        )
        assert d is not None
        await conn.execute(
            "update events.outbox_event set dispatched_at = now() where id = %s", (event_id,)
        )
        await spawn_sql(
            conn,
            queue="delivery",
            task_name="webhook.deliver",
            params={"delivery_id": str(d["id"]), "environment_id": str(principal.env)},
            idempotency_key=f"delivery:{d['id']}",
            max_attempts=3,
        )
    return {"event_id": env["id"], "delivery_id": d["id"]}


async def list_deliveries(
    platform: Platform,
    principal: Principal,
    endpoint_id: UUID,
    *,
    status: list[str] | None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    principal.require("webhooks:manage")
    async with tenant_tx(platform.pool, principal.env) as conn:
        await _get(conn, endpoint_id)
        rows = await fetch_all(
            conn,
            """select d.*, coalesce(json_agg(a order by a.attempt) filter (where a.id is not null), '[]') as
              attempts_log
                 from events.webhook_delivery d left join events.webhook_attempt a on a.delivery_id = d.id
                where d.endpoint_id = %s and (%s::text[] is null or d.status = any(%s))
                group by d.id order by d.created_at desc limit %s""",
            (endpoint_id, status, status, min(max(limit, 1), 500)),
        )
    for r in rows:
        r["event_id"] = public_event_id(r["event_id"])
    return rows


async def replay(platform: Platform, principal: Principal, delivery_id: UUID) -> dict[str, Any]:
    """HOOK-06: replay one delivery, including dead ones."""
    principal.require("webhooks:manage")
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await fetch_one(
            conn,
            """update events.webhook_delivery set status = 'PENDING', next_attempt_at = now(), attempts = 0
                where id = %s returning id, endpoint_id""",
            (delivery_id,),
        )
        if row is None:
            raise NotFoundError("Delivery not found", code="delivery_not_found")
        attempt = await fetch_one(
            conn,
            "select count(*) as n from events.webhook_attempt where delivery_id = %s",
            (delivery_id,),
        )
        await spawn_sql(
            conn,
            queue="delivery",
            task_name="webhook.deliver",
            params={"delivery_id": str(delivery_id), "environment_id": str(principal.env)},
            idempotency_key=f"delivery:{delivery_id}:replay:{attempt['n'] if attempt else 0}",
            max_attempts=3,
        )
        await audit(
            conn,
            principal,
            "webhook_delivery.replayed",
            target_kind="webhook_delivery",
            target_id=delivery_id,
        )
    return {"id": delivery_id, "status": "PENDING"}


async def replay_range(
    platform: Platform, principal: Principal, endpoint_id: UUID, *, since: Any, until: Any
) -> int:
    principal.require("webhooks:manage")
    async with tenant_tx(platform.pool, principal.env) as conn:
        await _get(conn, endpoint_id)
        rows = await fetch_all(
            conn,
            """select id from events.webhook_delivery where endpoint_id = %s
                                          and created_at >= %s and created_at <= coalesce(%s, now())""",
            (endpoint_id, since, until),
        )
    for r in rows:
        await replay(platform, principal, r["id"])
    return len(rows)


async def events_feed(
    platform: Platform,
    principal: Principal,
    *,
    after: str | None,
    types: list[str] | None,
    connection_id: UUID | None,
    limit: int = 100,
) -> dict[str, Any]:
    """``GET /v1/events``: the outbox as a pull feed, in id order."""
    principal.require("data:read")
    after_id = parse_event_id(after) if after else None
    async with tenant_tx(platform.pool, principal.env) as conn:
        rows = await fetch_all(
            conn,
            """select id, payload from events.outbox_event
                where (%s::uuid is null or id > %s) and (%s::text[] is null or type = any(%s))
                  and (%s::uuid is null or connection_id = %s)
                order by id limit %s""",
            (
                after_id,
                after_id,
                types,
                types,
                connection_id,
                connection_id,
                min(max(limit, 1), 500),
            ),
        )
    items = [r["payload"] for r in rows]
    return {"items": items, "next_cursor": items[-1]["id"] if items else after}


def dumps(v: Any) -> str:
    return json.dumps(v, default=str)
