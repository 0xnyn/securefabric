"""Connections: lifecycle, verification, credentials, health (part 3, sections 6-7).

States (CON-02)::

    PENDING ──verify ok──► ACTIVE ◄──resume── PAUSED ──delete──► DELETED ──30 d──► HARD_DELETED
       └──delete / abandoned 7 d──────────────────────────────────▲

The transition table is data; an illegal transition is a 409.
"""

import hashlib
import json
import re
from datetime import timedelta
from typing import Any
from uuid import UUID

import jsonschema
from psycopg import errors as pg_errors
from psycopg import sql

from securefabric_cdk.errors import ConnectorError
from securefabric_cdk.manifest import validate_options, version_at_least
from securefabric_core import (
    ConflictError,
    NotFoundError,
    ValidationFailedError,
    get_logger,
)
from securefabric_core.ids import uuid7
from securefabric_db import Conn, fetch_all, fetch_one, fetch_required, tenant_tx
from securefabric_domain.catalog import (
    ensure_default_integration,
    get_integration_row,
    resolve_vendor_app,
)
from securefabric_domain.events.outbox import emit
from securefabric_domain.paging import PageOut, clamp_limit, keyset_page
from securefabric_domain.runtime import Platform
from securefabric_domain.sync import health, jobs
from securefabric_domain.sync.bundle import budget_key_for, build_context, load_bundle
from securefabric_domain.sync.oplog import finish_operation, start_operation
from securefabric_domain.tenancy import Principal, audit
from securefabric_domain.vault import seal_for
from securefabric_schema import ConnectionState, GrantStatus, HealthCode
from securefabric_tasks.spec import spawn_sql

log = get_logger(__name__)

TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING": frozenset({"ACTIVE", "DELETED"}),
    "ACTIVE": frozenset({"PAUSED", "DELETED"}),
    "PAUSED": frozenset({"ACTIVE", "DELETED"}),
    "DELETED": frozenset({"HARD_DELETED"}),
    "HARD_DELETED": frozenset(),
}
PURGE_AFTER = timedelta(days=30)
ABANDONED_AFTER = timedelta(days=7)
METADATA_MAX_BYTES = 16 * 1024
MAX_TAGS = 10
_TAG_KEY = re.compile(r"^[A-Za-z0-9_.:/-]{1,64}$")


def check_transition(current: str, target: str) -> None:
    if target not in TRANSITIONS.get(current, frozenset()):
        raise ConflictError(
            f"A {current} connection cannot become {target}.",
            code="invalid_state_transition",
            current=current,
            target=target,
        )


def fingerprint(connector_id: str, vendor_app_id: str | None, tenant_identity: str) -> bytes:
    return hashlib.sha256(
        f"{connector_id}|{vendor_app_id or '-'}|{tenant_identity}".encode()
    ).digest()


def validate_metadata(metadata: dict[str, Any]) -> None:
    if len(json.dumps(metadata, separators=(",", ":")).encode()) > METADATA_MAX_BYTES:
        raise ValidationFailedError(
            "metadata is limited to 16 KB",
            code="metadata_too_large",
            errors=[{"field": "metadata", "message": "at most 16 KB"}],
        )


def validate_tags(tags: dict[str, Any]) -> dict[str, str]:
    if len(tags) > MAX_TAGS:
        raise ValidationFailedError(
            "at most 10 tags", code="too_many_tags", errors=[{"field": "tags", "message": "max 10"}]
        )
    out: dict[str, str] = {}
    for k, v in tags.items():
        if not _TAG_KEY.match(k) or not isinstance(v, str) or len(v) > 256:
            raise ValidationFailedError(
                f"invalid tag {k!r}",
                code="invalid_tag",
                errors=[{"field": f"tags.{k}", "message": "invalid"}],
            )
        out[k] = v
    return out


def validate_credentials(
    platform: Platform, connector_id: str, credentials: dict[str, Any]
) -> dict[str, Any]:
    schema = platform.registry.manifest(connector_id).credentials
    try:
        jsonschema.validate(credentials, schema)
    except jsonschema.ValidationError as exc:
        # Never echo the value: only the field path (SEC-07).
        field = ".".join(str(p) for p in exc.absolute_path) or "credentials"
        raise ValidationFailedError(
            "Invalid credentials",
            code="invalid_credentials",
            errors=[{"field": f"credentials.{field}", "message": f"{exc.validator} failed"}],
        ) from None
    return credentials


# ---------------------------------------------------------------- output shape


async def connection_out(
    platform: Platform, conn: Conn, row: dict[str, Any], *, detail: bool = False
) -> dict[str, Any]:
    manifest = platform.registry.manifest(row["connector_id"])
    out: dict[str, Any] = {
        "id": row["id"],
        "vendor": row["connector_id"],
        "connector_version": row["connector_version"],
        "identifier": row["identifier"],
        "organization_id": row["organization_id"],
        "integration_id": row["integration_id"],
        "state": row["state"],
        "is_active": row["state"] == "ACTIVE",
        "is_sandbox": row["is_sandbox"],
        "direction": row["direction"],
        "options": row["options"],
        "connection_config": {
            k: v
            for k, v in (row["connection_config"] or {}).items()
            if k not in ("permissions", "events")
        },
        "metadata": row["metadata"],
        "tags": row["tags"],
        "health": health.health_object(
            HealthCode(row["health_code"]), row["health_details"] or [], row["health_description"]
        ),
        "health_changed_at": row["health_changed_at"],
        "pending_detail": row.get("pending_detail"),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "deleted_at": row["deleted_at"],
    }
    if detail:
        cred = await fetch_one(
            conn,
            """select auth_mode, fields_set, rotated_at, last_refresh_at, refresh_exhausted,
                                               token_expires_at, updated_at from control.credential where
                                                 connection_id = %s""",
            (row["id"],),
        )
        out["authorization"] = {
            "auth_mode": cred["auth_mode"] if cred else manifest.auth.mode.value,
            "fields_set": cred["fields_set"] if cred else [],
            "rotated_at": cred["rotated_at"] if cred else None,
            "last_refresh_at": cred["last_refresh_at"] if cred else None,
            "refresh_exhausted": cred["refresh_exhausted"] if cred else False,
        }
        grants = {
            g["stream"]: g
            for g in await fetch_all(
                conn,
                "select * from control.connection_grant where connection_id = %s",
                (row["id"],),
            )
        }
        schedules = {
            s["stream"]: s
            for s in await fetch_all(
                conn, "select * from sync.stream_schedule where connection_id = %s", (row["id"],)
            )
        }
        heads = {
            h["stream"]: h
            for h in await fetch_all(
                conn, "select * from data.stream_head where connection_id = %s", (row["id"],)
            )
        }
        integ = await fetch_one(
            conn,
            "select enabled_streams from control.integration where id = %s",
            (row["integration_id"],),
        )
        enabled = set((integ or {}).get("enabled_streams") or [])
        out["streams"] = [
            {
                "name": s.name,
                "object": s.object,
                "enabled": s.name in enabled,
                "grant": grants[s.name]["status"] if s.name in grants else None,
                "grant_detail": grants[s.name]["detail"] if s.name in grants else None,
                "endpoint": grants[s.name]["endpoint"] if s.name in grants else s.endpoint,
                "interval_s": schedules[s.name]["interval_s"] if s.name in schedules else None,
                "schedule_state": schedules[s.name]["state"] if s.name in schedules else None,
                "next_run_at": schedules[s.name]["next_run_at"] if s.name in schedules else None,
                "last_success_at": schedules[s.name]["last_success_at"]
                if s.name in schedules
                else None,
                "record_count": heads[s.name]["live_count"] if s.name in heads else 0,
                "deleted_count": heads[s.name]["deleted_count"] if s.name in heads else 0,
                "capabilities": {k: v.model_dump() for k, v in s.capabilities.items()},
            }
            for s in manifest.streams
        ]
        out["refresh_interval_secs"] = min(
            (s["interval_s"] for s in schedules.values() if s["interval_s"]), default=None
        )
    return out


async def get_row(
    conn: Conn, connection_id: UUID, *, include_deleted: bool = False
) -> dict[str, Any]:
    row = await fetch_one(conn, "select * from control.connection where id = %s", (connection_id,))
    if row is None or (not include_deleted and row["deleted_at"] is not None):
        raise NotFoundError("Connection not found", code="connection_not_found")
    return row


# ---------------------------------------------------------------- create (CON-01)


async def create_connection(
    platform: Platform,
    principal: Principal,
    *,
    organization_id: UUID,
    vendor: str | None = None,
    integration: str | None = None,
    credentials: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
    identifier: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: dict[str, Any] | None = None,
    is_sandbox: bool = False,
    connect_session_id: UUID | None = None,
) -> dict[str, Any]:
    """Returns PENDING at once. Form connectors seal credentials and queue
    verification; redirect connectors (GitHub) return an ``authorize_url``."""
    principal.require("provisioning:write")
    if not vendor and not integration:
        raise ValidationFailedError(
            "Pass vendor or integration.",
            code="vendor_required",
            errors=[{"field": "vendor", "message": "required"}],
        )
    validate_metadata(metadata or {})
    tags_ = validate_tags(tags or {})
    env = principal.env
    async with tenant_tx(platform.pool, env) as conn:
        org = await fetch_one(
            conn,
            "select id from control.organization where id = %s and deleted_at is null",
            (organization_id,),
        )
        if org is None:
            raise NotFoundError("Organization not found", code="organization_not_found")
        if integration:
            integ = await get_integration_row(conn, integration)
        else:
            assert vendor is not None
            integ = await ensure_default_integration(platform, conn, env, vendor.upper())
        connector = platform.registry.get(integ["connector_id"])
        manifest = connector.manifest
        try:
            opts = validate_options(
                manifest, {**(integ["option_defaults"] or {}), **(options or {})}
            )
        except jsonschema.ValidationError as exc:
            raise ValidationFailedError(
                f"Invalid options: {exc.message}",
                code="invalid_options",
                errors=[{"field": "options", "message": exc.message}],
            ) from None
        redirect = manifest.auth.connect.value == "redirect" and not is_sandbox
        if not redirect and not is_sandbox:
            if credentials is None:
                raise ValidationFailedError(
                    "credentials are required for this connector",
                    code="credentials_required",
                    errors=[{"field": "credentials", "message": "required"}],
                )
            validate_credentials(platform, manifest.id, credentials)
        cid = uuid7()
        try:
            row = await fetch_one(
                conn,
                """insert into control.connection (id, environment_id, organization_id, integration_id, connector_id,
                       connector_version, identifier, state, options, metadata, tags, is_sandbox, connection_config)
                   values (%s, %s, %s, %s, %s, %s, %s, 'PENDING', %s, %s, %s, %s, %s) returning *""",
                (
                    cid,
                    env,
                    organization_id,
                    integ["id"],
                    manifest.id,
                    manifest.version,
                    identifier,
                    json.dumps(options or {}),
                    json.dumps(metadata or {}),
                    json.dumps(tags_),
                    is_sandbox,
                    json.dumps(
                        sandbox_config(platform, manifest.id)
                        if is_sandbox
                        else ({"region": opts.get("region")} if opts.get("region") else {})
                    ),
                ),
            )
        except pg_errors.UniqueViolation as exc:
            raise ConflictError(
                "This organization already has a connection with that identifier.",
                code="connection_identifier_exists",
            ) from exc
        assert row is not None
        sealed, version = (None, 1)
        if credentials:
            sealed, version = await seal_for(
                conn, env, connection_id=cid, purpose="credential", payload=credentials
            )
        await conn.execute(
            """insert into control.credential (connection_id, environment_id, auth_mode, sealed, vault_key_version,
              fields_set)
               values (%s, %s, %s, %s, %s, %s)""",
            (
                cid,
                env,
                manifest.auth.mode.value,
                sealed,
                version,
                sorted((credentials or {}).keys()),
            ),
        )
        await audit(
            conn,
            principal,
            "connection.created",
            target_kind="connection",
            target_id=cid,
            detail={
                "vendor": manifest.id,
                "integration_id": str(integ["id"]),
                "sandbox": is_sandbox,
            },
        )
        authorize_url = None
        if redirect:
            from securefabric_domain.connect import begin_redirect

            authorize_url = await begin_redirect(
                platform,
                conn,
                principal,
                connection=row,
                integration=integ,
                connect_session_id=connect_session_id,
            )
        else:
            await spawn_verify(conn, env, cid, "create")
        out = await connection_out(platform, conn, row)
    out["oauth2_authorize_url"] = authorize_url
    out["authorize_url"] = authorize_url
    return out


async def spawn_verify(
    conn: Conn, environment_id: UUID, connection_id: UUID, reason: str, *, staged: bool = False
) -> str:
    return await spawn_sql(
        conn,
        queue="control",
        task_name="connection.verify",
        params={
            "connection_id": str(connection_id),
            "environment_id": str(environment_id),
            "reason": reason,
            "staged": staged,
        },
        max_attempts=3,
    )


# ---------------------------------------------------------------- verify (control worker; AUTH-07/08/10)


async def verify_connection(
    platform: Platform,
    environment_id: UUID,
    connection_id: UUID,
    *,
    reason: str = "create",
    staged: bool = False,
) -> dict[str, Any]:
    """Call verify(), probe every enabled stream, record grants, fingerprint,
    duplicate check, activate. Returns ``{is_valid, message, grants}``."""
    async with tenant_tx(platform.pool, environment_id) as conn:
        bundle = await load_bundle(platform, conn, connection_id)
        staged_creds = None
        if staged:
            from securefabric_domain.vault import open_for

            cred = await fetch_one(
                conn,
                "select staged_sealed, vault_key_version from control.credential where connection_id = %s",
                (connection_id,),
            )
            if cred and cred["staged_sealed"]:
                staged_creds = await open_for(
                    platform,
                    conn,
                    environment_id,
                    cred["staged_sealed"],
                    version=cred["vault_key_version"],
                    connection_id=connection_id,
                    purpose="credential",
                )
    if bundle.connection["deleted_at"] is not None:
        return {
            "connection_id": str(connection_id),
            "is_valid": False,
            "message": "connection deleted",
            "grants": {},
        }
    op = await start_operation(
        platform.pool,
        environment_id=environment_id,
        kind="auth",
        action=f"verify:{reason}",
        connection_id=connection_id,
        organization_id=bundle.connection["organization_id"],
    )
    ctx = await build_context(
        platform,
        bundle,
        stream=None,
        op_log=op,
        capture=None,
        clock=platform.clock,
        interactive=True,
        credentials_override=staged_creds,
    )
    grants: dict[str, tuple[GrantStatus, str | None, str | None]] = {}
    try:
        result = await bundle.connector.verify(ctx)
        ctx.config.update(result.config_updates)
        enabled = [
            s for s in bundle.integration["enabled_streams"] if s in bundle.manifest.stream_names
        ]
        server_version = ctx.config.get("server_version")
        for stream in enabled:
            minimum = bundle.manifest.stream(stream).min_vendor_version
            if not version_at_least(server_version, minimum):
                # Self-hosted vendors (GHES): the endpoint does not exist on this release.
                grants[stream] = (
                    GrantStatus.UNSUPPORTED,
                    None,
                    f"needs {bundle.manifest.display_name} {minimum} or later; "
                    f"this instance runs {server_version}",
                )
                continue
            try:
                g = await bundle.connector.probe(ctx, stream)
                grants[stream] = (g.status, g.endpoint, g.detail)
            except ConnectorError as exc:
                grants[stream] = (GrantStatus.UNKNOWN, None, exc.message[:300])
    except ConnectorError as exc:
        await ctx.http.aclose()
        message = exc.message
        op.log("error", f"verification failed: {message}")
        await finish_operation(
            platform.pool,
            op,
            status="failed",
            summary={"reason": reason, "error": message, "health_code": exc.health_code.value},
        )
        async with tenant_tx(platform.pool, environment_id) as conn:
            row = await get_row(conn, connection_id)
            if reason == "create" and row["state"] == "PENDING":
                await conn.execute(
                    "update control.connection set pending_detail = %s, updated_at = now() where id = %s",
                    (message[:500], connection_id),
                )
                await emit(
                    conn,
                    environment_id=environment_id,
                    connection_id=connection_id,
                    type="connection.create.failed",
                    data={
                        "vendor": row["connector_id"],
                        "error": exc.health_code.value,
                        "description": message,
                    },
                )
            elif reason in ("rotate",):
                await conn.execute(
                    "update control.credential set staged_sealed = null where connection_id = %s",
                    (connection_id,),
                )
            elif row["state"] == "ACTIVE" and reason not in ("test",):
                await health.recompute(
                    conn, connection_id, override=exc.health_code, override_detail=message
                )
        return {
            "connection_id": str(connection_id),
            "is_valid": False,
            "message": message,
            "health_code": exc.health_code.value,
            "grants": {},
        }
    await ctx.http.aclose()
    grant_out = {k: v[0].value for k, v in grants.items()}
    if reason == "test":
        await finish_operation(
            platform.pool, op, status="success", summary={"reason": reason, "grants": grant_out}
        )
        return {
            "connection_id": str(connection_id),
            "is_valid": True,
            "message": result.display_name,
            "grants": grant_out,
        }

    vendor_app_id = str(bundle.vendor_app["id"]) if bundle.vendor_app else None
    fp = fingerprint(bundle.manifest.id, vendor_app_id, result.tenant_identity)
    async with tenant_tx(platform.pool, environment_id) as conn:
        row = await fetch_required(
            conn, "select * from control.connection where id = %s for update", (connection_id,)
        )
        assert row is not None
        dup = await fetch_one(
            conn,
            """select id from control.connection where organization_id = %s and integration_id = %s
                  and tenant_fingerprint = %s and deleted_at is null and id <> %s""",
            (row["organization_id"], row["integration_id"], fp, connection_id),
        )
        if dup is not None:
            vendor = bundle.manifest.display_name
            message = f"This organization is already connected to that {vendor} tenant (connection {dup['id']})."
            await conn.execute(
                "update control.connection set pending_detail = %s where id = %s",
                (message, connection_id),
            )
            if reason == "create":
                await emit(
                    conn,
                    environment_id=environment_id,
                    connection_id=connection_id,
                    type="connection.create.failed",
                    data={
                        "vendor": row["connector_id"],
                        "error": "DUPLICATE_CONNECTION",
                        "description": message,
                    },
                )
            await finish_operation(
                platform.pool, op, status="failed", summary={"reason": reason, "error": "duplicate"}
            )
            return {
                "connection_id": str(connection_id),
                "is_valid": False,
                "message": message,
                "grants": grant_out,
            }
        config = {**(row["connection_config"] or {}), **result.config_updates}
        await conn.execute(
            """update control.connection set connection_config = %s, vendor_tenant_ref = coalesce(%s,
              vendor_tenant_ref),
                      tenant_fingerprint = %s, pending_detail = null, updated_at = now() where id = %s""",
            (json.dumps(config), result.vendor_tenant_ref, fp, connection_id),
        )
        for stream, (status, endpoint, detail) in grants.items():
            await conn.execute(
                """insert into control.connection_grant (connection_id, environment_id, stream, status, endpoint,
                  detail, checked_at)
                   values (%s, %s, %s, %s, %s, %s, now())
                   on conflict (connection_id, stream) do update set status = excluded.status, endpoint =
                     excluded.endpoint,
                        detail = excluded.detail, checked_at = now()""",
                (connection_id, environment_id, stream, status.value, endpoint, detail),
            )
        if staged:
            await conn.execute(
                """update control.credential set sealed = staged_sealed, staged_sealed = null, rotated_at = now(),
                          token_sealed = null, refresh_exhausted = false, refresh_fail_days = 0 where connection_id =
                            %s""",
                (connection_id,),
            )
        key = await budget_key_for(platform, conn, connection_id)
        if row["state"] == "PENDING":
            await conn.execute(
                "update control.connection set state = 'ACTIVE', pending_detail = null, "
                "updated_at = now() where id = %s",
                (connection_id,),
            )
            row = await get_row(conn, connection_id)
            await jobs.initial_job(platform, conn, row, key)
            if row["health_code"] not in (None, HealthCode.INITIALIZING.value):
                # An earlier attempt crashed (INTERNAL_ERROR); the first sync decides now.
                await health.recompute(conn, connection_id)
            await emit(
                conn,
                environment_id=environment_id,
                connection_id=connection_id,
                type="connection.create.succeeded",
                data={
                    "vendor": row["connector_id"],
                    "error": None,
                    "description": result.display_name,
                    "grants": grant_out,
                },
            )
            await conn.execute(
                "insert into obs.usage_event (environment_id, kind, detail) values (%s, 'connection.active', %s)",
                (
                    environment_id,
                    json.dumps(
                        {"connection_id": str(connection_id), "vendor": row["connector_id"]}
                    ),
                ),
            )
        elif row["state"] == "ACTIVE" and reason in ("reprobe", "restore", "reauthorize", "rotate"):
            integ = await fetch_one(
                conn, "select * from control.integration where id = %s", (row["integration_id"],)
            )
            assert integ is not None
            await jobs.ensure_schedules(
                conn, row, integ, bundle.manifest, row["options"] or {}, platform.clock.now()
            )
            if reason in ("restore", "reauthorize"):
                await jobs.set_schedules_state(conn, connection_id, "STARTED")
            newly = [s for s, (st, _, _) in grants.items() if st is GrantStatus.GRANTED]
            from securefabric_schema import Mode

            await jobs.create_job(
                conn,
                row,
                job_type="ON_DEMAND",
                runs=[
                    (
                        s,
                        await jobs.mode_for(
                            conn,
                            bundle.manifest,
                            connection_id,
                            s,
                            force_full=False,
                            now=platform.clock.now(),
                        ),
                    )
                    for s in newly
                ],
                priority=jobs.PRIORITY_INITIAL,
                budget_key=key,
                requested_by=f"verify:{reason}",
                now=platform.clock.now(),
            )
            _ = Mode
        await health.recompute(conn, connection_id)
    await finish_operation(
        platform.pool,
        op,
        status="success",
        summary={"reason": reason, "grants": grant_out, "tenant": result.display_name},
    )
    return {
        "connection_id": str(connection_id),
        "is_valid": True,
        "message": result.display_name,
        "grants": grant_out,
    }


# ---------------------------------------------------------------- read


async def get_connection(
    platform: Platform, principal: Principal, connection_id: UUID
) -> dict[str, Any]:
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await get_row(conn, connection_id)
        if principal.organization_id and row["organization_id"] != principal.organization_id:
            raise NotFoundError("Connection not found", code="connection_not_found")
        return await connection_out(platform, conn, row, detail=True)


async def list_connections(
    platform: Platform,
    principal: Principal,
    *,
    organization_id: UUID | None = None,
    vendor: list[str] | None = None,
    state: list[str] | None = None,
    health_status: list[str] | None = None,
    health_codes: list[str] | None = None,
    tags: dict[str, str] | None = None,
    integration_id: UUID | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> PageOut[dict[str, Any]]:
    principal.require("provisioning:read")
    where: list[sql.Composable] = [sql.SQL("c.deleted_at is null")]
    params: list[Any] = []
    if state:
        where = [sql.SQL("c.state = any(%s)")]
        params.append([s.upper() for s in state])
        if "DELETED" not in [s.upper() for s in state]:
            where.append(sql.SQL("c.deleted_at is null"))
    for col, val in (("c.organization_id", organization_id), ("c.integration_id", integration_id)):
        if val:
            where.append(sql.SQL(f"{col} = %s"))
            params.append(val)
    for col, vals in (
        ("c.connector_id", vendor),
        ("c.health_status", health_status),
        ("c.health_code", health_codes),
    ):
        if vals:
            where.append(sql.SQL(f"{col} = any(%s)"))
            params.append([v.upper() for v in vals])
    if tags:
        where.append(sql.SQL("c.tags @> %s::jsonb"))
        params.append(json.dumps(tags))
    filters = {
        "organizationId": str(organization_id) if organization_id else None,
        "vendor": vendor,
        "state": state,
        "healthStatus": health_status,
        "healthStatusCodes": health_codes,
        "tags": tags,
        "integrationId": str(integration_id) if integration_id else None,
    }
    async with tenant_tx(platform.pool, principal.env) as conn:
        page = await keyset_page(
            conn,
            key=platform.cursor_key,
            base=sql.SQL("select c.* from control.connection c"),
            where=where,
            params=params,
            sort_name="created_at:asc",
            sort_exprs=["c.created_at", "c.id"],
            sort_keys=lambda r: [r["created_at"], str(r["id"])],
            descending=False,
            cursor_token=cursor,
            filters=filters,
            scope=f"connections:{principal.env}",
            limit=clamp_limit(limit),
        )
        items = [await connection_out(platform, conn, r) for r in page.items]
    return PageOut(items, page.next_cursor, page.previous_cursor)


async def health_history(
    platform: Platform, principal: Principal, connection_id: UUID
) -> list[dict[str, Any]]:
    """CON-14: 30 days served by the API."""
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        await get_row(conn, connection_id, include_deleted=True)
        return await fetch_all(
            conn,
            """select from_code, to_code, details, job_id, at from control.connection_health_event
                where connection_id = %s and at > now() - interval '30 days' order by at desc""",
            (connection_id,),
        )


# ---------------------------------------------------------------- update


async def update_connection(
    platform: Platform, principal: Principal, connection_id: UUID, changes: dict[str, Any]
) -> dict[str, Any]:
    principal.require("provisioning:write")
    env = principal.env
    async with tenant_tx(platform.pool, env) as conn:
        row = await fetch_one(
            conn,
            "select * from control.connection where id = %s and deleted_at is null for update",
            (connection_id,),
        )
        if row is None:
            raise NotFoundError("Connection not found", code="connection_not_found")
        manifest = platform.registry.manifest(row["connector_id"])
        if "options" in changes and changes["options"] is not None:
            integ = await fetch_one(
                conn, "select * from control.integration where id = %s", (row["integration_id"],)
            )
            assert integ is not None
            merged = {**(row["options"] or {}), **changes["options"]}
            try:
                validate_options(manifest, {**(integ["option_defaults"] or {}), **merged})
            except jsonschema.ValidationError as exc:
                raise ValidationFailedError(
                    f"Invalid options: {exc.message}",
                    code="invalid_options",
                    errors=[{"field": "options", "message": exc.message}],
                ) from None
            await conn.execute(
                "update control.connection set options = %s, updated_at = now() where id = %s",
                (json.dumps(merged), connection_id),
            )
            row["options"] = merged
            if row["state"] == "ACTIVE":
                await jobs.ensure_schedules(
                    conn, row, integ, manifest, merged, platform.clock.now()
                )
        if "tags" in changes and changes["tags"] is not None:
            await conn.execute(
                "update control.connection set tags = %s, updated_at = now() where id = %s",
                (json.dumps(validate_tags(changes["tags"])), connection_id),
            )
        if "identifier" in changes and changes["identifier"] is not None:
            try:
                await conn.execute(
                    "update control.connection set identifier = %s, updated_at = now() where id = %s",
                    (changes["identifier"], connection_id),
                )
            except pg_errors.UniqueViolation as exc:
                raise ConflictError(
                    "Identifier already used in this organization.",
                    code="connection_identifier_exists",
                ) from exc
        if changes.get("credentials") is not None:
            # AUTH-11: seal into staging, verify, swap only on success.
            creds = validate_credentials(platform, manifest.id, changes["credentials"])
            sealed, version = await seal_for(
                conn, env, connection_id=connection_id, purpose="credential", payload=creds
            )
            await conn.execute(
                "update control.credential set staged_sealed = %s, vault_key_version = %s, fields_set = %s where "
                "connection_id = %s",
                (sealed, version, sorted(creds), connection_id),
            )
            await spawn_verify(conn, env, connection_id, "rotate", staged=True)
        target = (changes.get("state") or "").upper()
        if target and target != row["state"]:
            check_transition(row["state"], target)
            if target == "PAUSED":
                await _pause(conn, row, platform)
            elif target == "ACTIVE":
                await _resume(platform, conn, row)
            elif target == "DELETED":
                await _delete(platform, conn, row)
        await audit(
            conn,
            principal,
            "connection.updated",
            target_kind="connection",
            target_id=connection_id,
            detail={"fields": sorted(k for k, v in changes.items() if v is not None)},
        )
        row = await get_row(conn, connection_id, include_deleted=True)
        return await connection_out(platform, conn, row, detail=True)


async def _pause(conn: Conn, row: dict[str, Any], platform: Platform) -> None:
    """CON-03: schedules pause; a running run finishes its page and stops; data stays readable."""
    await conn.execute(
        "update control.connection set state = 'PAUSED', updated_at = now() where id = %s",
        (row["id"],),
    )
    await jobs.set_schedules_state(conn, row["id"], "PAUSED")
    await conn.execute(
        """update sync.stream_run set state = 'CANCELLED', finished_at = now(), warning = 'connection paused'
            where connection_id = %s and state in ('QUEUED', 'PARKED', 'RETRY_WAIT')""",
        (row["id"],),
    )
    await conn.execute(
        "update sync.stream_run set cancel_requested = true where connection_id = %s and state in ('ADMITTED', "
        "'RUNNING')",
        (row["id"],),
    )
    await emit(
        conn,
        environment_id=row["environment_id"],
        connection_id=row["id"],
        type="connection.paused",
        data={"vendor": row["connector_id"]},
    )


async def _resume(platform: Platform, conn: Conn, row: dict[str, Any]) -> None:
    await conn.execute(
        "update control.connection set state = 'ACTIVE', updated_at = now() where id = %s",
        (row["id"],),
    )
    await jobs.set_schedules_state(conn, row["id"], "STARTED")
    row = await get_row(conn, row["id"])
    manifest = platform.registry.manifest(row["connector_id"])
    integ = await fetch_one(
        conn, "select * from control.integration where id = %s", (row["integration_id"],)
    )
    assert integ is not None
    streams = [s for s in integ["enabled_streams"] if s in manifest.stream_names]
    now = platform.clock.now()
    runs = [
        (s, await jobs.mode_for(conn, manifest, row["id"], s, force_full=False, now=now))
        for s in streams
    ]
    await jobs.create_job(
        conn,
        row,
        job_type="ON_DEMAND",
        runs=runs,
        priority=jobs.PRIORITY_INITIAL,
        budget_key=await budget_key_for(platform, conn, row["id"]),
        requested_by="resume",
        now=now,
    )
    await emit(
        conn,
        environment_id=row["environment_id"],
        connection_id=row["id"],
        type="connection.resumed",
        data={"vendor": row["connector_id"]},
    )


async def _delete(platform: Platform, conn: Conn, row: dict[str, Any]) -> None:
    """CON-04, in one transaction: state DELETED, credential row deleted, schedules
    deleted, purge in 30 days, ``connection.deleted`` in the outbox."""
    now = platform.clock.now()
    await conn.execute(
        """update control.connection set state = 'DELETED', deleted_at = %s, purge_after = %s, updated_at = now()
            where id = %s""",
        (now, now + PURGE_AFTER, row["id"]),
    )
    await conn.execute("delete from control.credential where connection_id = %s", (row["id"],))
    await conn.execute("delete from sync.stream_schedule where connection_id = %s", (row["id"],))
    await conn.execute("delete from sync.dirty_record where connection_id = %s", (row["id"],))
    await conn.execute(
        """update sync.stream_run set state = 'CANCELLED', finished_at = %s, warning = 'connection deleted'
            where connection_id = %s and state in ('QUEUED', 'PARKED', 'RETRY_WAIT')""",
        (now, row["id"]),
    )
    await conn.execute(
        "update sync.stream_run set cancel_requested = true where connection_id = %s and state in ('ADMITTED', "
        "'RUNNING')",
        (row["id"],),
    )
    await emit(
        conn,
        environment_id=row["environment_id"],
        connection_id=row["id"],
        type="connection.deleted",
        data={"vendor": row["connector_id"], "purge_after": (now + PURGE_AFTER).isoformat()},
    )


async def delete_connection(platform: Platform, principal: Principal, connection_id: UUID) -> None:
    await update_connection(platform, principal, connection_id, {"state": "DELETED"})


async def set_metadata(
    platform: Platform,
    principal: Principal,
    connection_id: UUID,
    metadata: dict[str, Any],
    *,
    merge: bool,
) -> dict[str, Any]:
    """CON-10: replace (PUT) or merge (PATCH), 16 KB cap."""
    principal.require("provisioning:write")
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await get_row(conn, connection_id)
        new = {**(row["metadata"] or {}), **metadata} if merge else metadata
        validate_metadata(new)
        await conn.execute(
            "update control.connection set metadata = %s, updated_at = now() where id = %s",
            (json.dumps(new), connection_id),
        )
        await audit(
            conn,
            principal,
            "connection.metadata_updated",
            target_kind="connection",
            target_id=connection_id,
        )
        return new


async def run_connection_test(
    platform: Platform, principal: Principal, connection_id: UUID, *, wait_s: float = 30.0
) -> dict[str, Any]:
    """CON-11: run verification in a control worker and wait up to 30 s. A vendor
    rejection is ``is_valid: false``, not an error."""
    import asyncio

    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await get_row(conn, connection_id)
        # Testing a connection that never activated retries its creation, so it can activate.
        reason = "create" if row["state"] == ConnectionState.PENDING else "test"
        task_id = await spawn_verify(conn, principal.env, connection_id, reason)
    deadline = asyncio.get_running_loop().time() + wait_s
    while asyncio.get_running_loop().time() < deadline:
        async with platform.pool.connection() as conn:
            snap = await fetch_one(
                conn, "select state, result from absurd.get_task_result('control', %s)", (task_id,)
            )
        if snap and snap["state"] in ("completed", "failed", "cancelled"):
            if snap["state"] == "completed" and snap["result"]:
                result: dict[str, Any] = snap["result"]
                return {
                    "is_valid": result.get("is_valid", False),
                    "message": result.get("message"),
                    "grants": result.get("grants", {}),
                }
            return {"is_valid": False, "message": "verification could not complete", "grants": {}}
        await asyncio.sleep(0.25)
    return {
        "is_valid": False,
        "message": "verification is still running; try again shortly",
        "grants": {},
        "pending": True,
    }


async def vendor_app_for(conn: Conn, row: dict[str, Any]) -> dict[str, Any] | None:
    integ = await fetch_one(
        conn, "select * from control.integration where id = %s", (row["integration_id"],)
    )
    return await resolve_vendor_app(conn, integ) if integ else None


def is_state(value: str) -> bool:
    return value in ConnectionState.__members__


VERIFY_CRASH_DETAIL = (
    "Verification failed with an internal error. SecureFabric has been alerted; "
    "test the connection again to retry."
)


async def record_verify_crash(
    platform: Platform,
    environment_id: UUID,
    connection_id: UUID,
    *,
    reason: str,
    error: BaseException,
    final: bool,
) -> None:
    """A verification task raised something other than a classified connector error.

    Every attempt is logged. On the final attempt the outcome is made visible instead
    of leaving the connection silently PENDING: health INTERNAL_ERROR (owner PLATFORM),
    ``connection.create.failed`` for a creation, the staged credential discarded for a
    rotation, and an ``internal_error`` alert for us.
    """
    from securefabric_domain.sync.scheduler import raise_alert

    # Exception text can carry anything, credentials included, and redaction only knows
    # patterns: keep just the type. The traceback stays on the Absurd run for operators.
    error_type = type(error).__name__
    log.error(
        "verify_crashed",
        connection_id=str(connection_id),
        reason=reason,
        error_type=error_type,
        final=final,
    )
    if not final:
        return
    async with tenant_tx(platform.pool, environment_id) as conn:
        row = await fetch_one(
            conn, "select * from control.connection where id = %s for update", (connection_id,)
        )
        if row is None or row["deleted_at"] is not None:
            return
        if reason == "rotate":
            await conn.execute(
                "update control.credential set staged_sealed = null where connection_id = %s",
                (connection_id,),
            )
        elif reason != "test":
            await health.recompute(
                conn,
                connection_id,
                override=HealthCode.INTERNAL_ERROR,
                override_detail=VERIFY_CRASH_DETAIL,
            )
        if row["state"] == ConnectionState.PENDING and reason == "create":
            await conn.execute(
                "update control.connection set pending_detail = %s, updated_at = now() where id = %s",
                (VERIFY_CRASH_DETAIL, connection_id),
            )
            await emit(
                conn,
                environment_id=environment_id,
                connection_id=connection_id,
                type="connection.create.failed",
                data={
                    "vendor": row["connector_id"],
                    "error": HealthCode.INTERNAL_ERROR.value,
                    "description": VERIFY_CRASH_DETAIL,
                },
            )
    async with platform.sys_pool.connection() as conn, conn.transaction():
        await raise_alert(
            conn,
            "internal_error",
            f"verify:{connection_id}",
            {
                "reason": reason,
                "error_type": error_type,
                "environment_id": str(environment_id),
                "where": "absurd.r_control failure_reason for this connection's verify task",
            },
        )


def sandbox_config(platform: Platform, connector_id: str) -> dict[str, Any]:
    """The connection config the recorded fixtures were made with (``fixtures/
    connection.json``), so a sandbox connection verifies and lists exactly what was
    recorded (TEN-13). Connectors with an in-process vendor need none."""
    path = platform.registry.get(connector_id).package_dir() / "fixtures" / "connection.json"
    if not path.exists():
        return {}
    config: dict[str, Any] = json.loads(path.read_text())
    return config
