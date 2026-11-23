"""Catalogue, integrations and vendor apps (CAT-01, CAT-02, PD-3, PD-10).

- A **connector** is code plus a manifest, global and versioned.
- An **integration** is one environment's use of a connector: enabled streams,
  default intervals, option defaults, which vendor app, write-back.
- A **vendor app** is a registration with a vendor (a GitHub App). Platform-owned
  apps (``environment_id is null``) are shared; customer-owned apps are required
  for GHES and GHE.com.
"""

import json
from typing import Any
from uuid import UUID

import jsonschema
from psycopg import errors as pg_errors

from securefabric_cdk.egress import check_url
from securefabric_cdk.errors import EgressDenied
from securefabric_cdk.manifest import Manifest, option_defaults, options_schema
from securefabric_core import ConflictError, NotFoundError, ValidationFailedError, get_logger
from securefabric_db import Conn, fetch_all, fetch_one, fetch_required, system_tx, tenant_tx
from securefabric_domain.runtime import Platform
from securefabric_domain.tenancy import Principal, audit
from securefabric_domain.vault import seal_for, seal_platform

log = get_logger(__name__)


# ---------------------------------------------------------------- connectors (public)


def connector_public(
    manifest: Manifest, capabilities: dict[str, Any] | None = None
) -> dict[str, Any]:
    """CAT-01: id, name, categories, auth, credential schema, data types, docs."""
    return {
        "id": manifest.id,
        "version": manifest.version,
        "name": manifest.display_name,
        "description": manifest.description,
        "categories": manifest.categories,
        "status": manifest.status,
        "logo_url": manifest.logo,
        "docs_url": manifest.docs_url,
        "auth": {
            "mode": manifest.auth.mode.value,
            "connect": manifest.auth.connect.value,
            "vendor_app": manifest.auth.vendor_app,
        },
        "credentials_schema": manifest.credentials,
        "connection_config_schema": manifest.connection_config,
        "options_schema": options_schema(manifest),
        "regions": [r.model_dump() for r in manifest.regions],
        "permissions": [p.model_dump() for p in manifest.permissions],
        "streams": [
            {
                "name": s.name,
                "title": s.title or s.name.replace("_", " ").title(),
                "object": s.object,
                "finding_types": [t.value for t in s.finding_types],
                "resource_types": [t.value for t in s.resource_types],
                "sync_mode": s.sync_mode.value,
                "deletion": s.deletion.value,
                "interval": s.interval.model_dump(),
                "vendor_retention_s": s.vendor_retention,
                "natural_key": s.natural_key,
                "webhook_events": s.webhook_events,
                "capabilities": {k: v.model_dump() for k, v in s.capabilities.items()},
                "enabled_by_default": s.enabled_by_default,
                "cost": s.cost,
            }
            for s in manifest.streams
        ],
        "actions": [a.model_dump() for a in manifest.actions],
        "data_types": sorted({s.object for s in manifest.streams}),
        "capabilities": capabilities or {},
    }


def list_connectors(platform: Platform) -> list[dict[str, Any]]:
    from securefabric_domain.capabilities import connector_capabilities

    return [
        connector_public(c.manifest, connector_capabilities(c.manifest.id))
        for c in platform.registry.all()
    ]


def get_connector(platform: Platform, connector_id: str) -> dict[str, Any]:
    from securefabric_domain.capabilities import connector_capabilities

    m = platform.registry.manifest(connector_id)
    return connector_public(m, connector_capabilities(m.id))


# ---------------------------------------------------------------- integrations


def _integration_out(row: dict[str, Any], manifest: Manifest) -> dict[str, Any]:
    from securefabric_domain.capabilities import connector_capabilities

    return {
        "id": row["id"],
        "key": row["key"],
        "connector_id": row["connector_id"],
        "connector_version": manifest.version,
        "deprecated": manifest.status == "deprecated",
        "display_name": row["display_name"],
        "vendor_app_id": row["vendor_app_id"],
        "enabled_streams": row["enabled_streams"],
        "stream_intervals": row["stream_intervals"],
        "option_defaults": row["option_defaults"],
        "options_schema": options_schema(manifest),
        "write_back_enabled": row["write_back_enabled"],
        "capabilities": connector_capabilities(manifest.id),
        "created_at": row["created_at"],
    }


def _validate_integration(
    manifest: Manifest,
    *,
    enabled_streams: list[str] | None,
    stream_intervals: dict[str, int] | None,
    option_defaults_: dict[str, Any] | None,
    write_back_enabled: bool | None,
) -> None:
    errors: list[dict[str, str]] = []
    for s in enabled_streams or []:
        if s not in manifest.stream_names:
            errors.append({"field": "enabled_streams", "message": f"unknown stream {s!r}"})
    for s, iv in (stream_intervals or {}).items():
        if s not in manifest.stream_names:
            errors.append({"field": "stream_intervals", "message": f"unknown stream {s!r}"})
            continue
        spec = manifest.stream(s).interval
        if not spec.min <= iv <= spec.max:
            errors.append(
                {"field": f"stream_intervals.{s}", "message": f"must be {spec.min}..{spec.max}s"}
            )
        retention = manifest.stream(s).vendor_retention
        if retention is not None and iv > retention:
            errors.append(
                {
                    "field": f"stream_intervals.{s}",
                    "message": f"exceeds vendor retention {retention}s (SYNC-18)",
                }
            )
    if option_defaults_:
        try:
            jsonschema.validate(
                {**option_defaults(manifest.options), **option_defaults_}, options_schema(manifest)
            )
        except jsonschema.ValidationError as exc:
            errors.append({"field": "option_defaults", "message": exc.message})
    if write_back_enabled and not manifest.actions:
        errors.append(
            {"field": "write_back_enabled", "message": "this connector declares no actions"}
        )
    if errors:
        raise ValidationFailedError(
            "Invalid integration", code="invalid_integration", errors=errors
        )


async def ensure_default_integration(
    platform: Platform, conn: Conn, environment_id: UUID, connector_id: str
) -> dict[str, Any]:
    """Leen path: ``vendor: "GITHUB"`` resolves to the default integration, created on first use."""
    manifest = platform.registry.manifest(connector_id)
    key = manifest.id.lower()
    row = await fetch_one(
        conn, "select * from control.integration where key = %s and deleted_at is null", (key,)
    )
    if row:
        return row
    row = await fetch_one(
        conn,
        """insert into control.integration (environment_id, connector_id, key, display_name, enabled_streams)
           values (%s, %s, %s, %s, %s)
           on conflict (environment_id, key) where deleted_at is null do update set key = excluded.key
           returning *""",
        (environment_id, manifest.id, key, manifest.display_name, manifest.default_streams()),
    )
    assert row is not None
    return row


async def create_integration(
    platform: Platform,
    principal: Principal,
    *,
    connector_id: str,
    key: str | None,
    display_name: str | None,
    vendor_app_id: UUID | None,
    enabled_streams: list[str] | None,
    stream_intervals: dict[str, int] | None,
    option_defaults_: dict[str, Any] | None,
    write_back_enabled: bool,
) -> dict[str, Any]:
    principal.require("provisioning:write")
    manifest = platform.registry.manifest(connector_id)
    _validate_integration(
        manifest,
        enabled_streams=enabled_streams,
        stream_intervals=stream_intervals,
        option_defaults_=option_defaults_,
        write_back_enabled=write_back_enabled,
    )
    async with tenant_tx(platform.pool, principal.env) as conn:
        if vendor_app_id is not None:
            await get_vendor_app_row(conn, vendor_app_id, connector_id=manifest.id)
        try:
            row = await fetch_one(
                conn,
                """insert into control.integration (environment_id, connector_id, key, display_name,
                     vendor_app_id, enabled_streams, stream_intervals, option_defaults, write_back_enabled)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
                (
                    principal.env,
                    manifest.id,
                    key or manifest.id.lower(),
                    display_name or manifest.display_name,
                    vendor_app_id,
                    enabled_streams or manifest.default_streams(),
                    json.dumps(stream_intervals or {}),
                    json.dumps(option_defaults_ or {}),
                    write_back_enabled,
                ),
            )
        except pg_errors.UniqueViolation as exc:
            raise ConflictError(
                "An integration with that key already exists.", code="integration_exists"
            ) from exc
        assert row is not None
        await audit(
            conn, principal, "integration.created", target_kind="integration", target_id=row["id"]
        )
    return _integration_out(row, manifest)


async def list_integrations(platform: Platform, principal: Principal) -> list[dict[str, Any]]:
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        rows = await fetch_all(
            conn, "select * from control.integration where deleted_at is null order by created_at"
        )
    return [_integration_out(r, platform.registry.manifest(r["connector_id"])) for r in rows]


async def get_integration_row(conn: Conn, integration_ref: str | UUID) -> dict[str, Any]:
    try:
        uid = UUID(str(integration_ref))
        row = await fetch_one(
            conn, "select * from control.integration where id = %s and deleted_at is null", (uid,)
        )
    except ValueError:
        row = await fetch_one(
            conn,
            "select * from control.integration where key = %s and deleted_at is null",
            (str(integration_ref),),
        )
    if row is None:
        raise NotFoundError("Integration not found", code="integration_not_found")
    return row


async def get_integration(
    platform: Platform, principal: Principal, integration_ref: str
) -> dict[str, Any]:
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await get_integration_row(conn, integration_ref)
    return _integration_out(row, platform.registry.manifest(row["connector_id"]))


async def update_integration(
    platform: Platform, principal: Principal, integration_ref: str, changes: dict[str, Any]
) -> dict[str, Any]:
    principal.require("provisioning:write")
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await get_integration_row(conn, integration_ref)
        manifest = platform.registry.manifest(row["connector_id"])
        _validate_integration(
            manifest,
            enabled_streams=changes.get("enabled_streams"),
            stream_intervals=changes.get("stream_intervals"),
            option_defaults_=changes.get("option_defaults"),
            write_back_enabled=changes.get("write_back_enabled"),
        )
        if changes.get("vendor_app_id"):
            await get_vendor_app_row(conn, changes["vendor_app_id"], connector_id=manifest.id)
        sets, args = [], []
        for col in ("display_name", "vendor_app_id", "enabled_streams", "write_back_enabled"):
            if col in changes:
                sets.append(f"{col} = %s")
                args.append(changes[col])
        for col in ("stream_intervals", "option_defaults"):
            if col in changes:
                sets.append(f"{col} = %s")
                args.append(json.dumps(changes[col]))
        if sets:
            row = await fetch_required(
                conn,
                f"update control.integration set {', '.join(sets)} where id = %s returning *",  # noqa: S608
                (*args, row["id"]),
            )
            assert row is not None
            await audit(
                conn,
                principal,
                "integration.updated",
                target_kind="integration",
                target_id=row["id"],
                detail={"fields": sorted(changes)},
            )
        if "enabled_streams" in changes or "stream_intervals" in changes:
            from securefabric_domain.sync.jobs import reconcile_integration_schedules

            await reconcile_integration_schedules(platform, conn, row)
    return _integration_out(row, manifest)


async def delete_integration(
    platform: Platform, principal: Principal, integration_ref: str
) -> None:
    principal.require("provisioning:write")
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await get_integration_row(conn, integration_ref)
        live = await fetch_one(
            conn,
            "select count(*) as n from control.connection where integration_id = %s and deleted_at is null",
            (row["id"],),
        )
        if live and live["n"]:
            raise ConflictError(
                "The integration has live connections.", code="integration_has_connections"
            )
        await conn.execute(
            "update control.integration set deleted_at = now() where id = %s", (row["id"],)
        )
        await audit(
            conn, principal, "integration.deleted", target_kind="integration", target_id=row["id"]
        )


# ---------------------------------------------------------------- vendor apps


def vendor_app_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "connector_id": row["connector_id"],
        "name": row["name"],
        "base_url": row["base_url"],
        "config": row["config"],
        "owner": "platform" if row["environment_id"] is None else "environment",
        "is_default": row.get("is_default", False),
        "secrets_set": bool(row.get("secrets_sealed")),
        "webhook_secret_set": bool(row.get("ingress_secret_enc")),
        "created_at": row["created_at"],
    }


async def get_vendor_app_row(
    conn: Conn, vendor_app_id: UUID, *, connector_id: str | None = None
) -> dict[str, Any]:
    row = await fetch_one(
        conn,
        "select * from control.vendor_app where id = %s and deleted_at is null",
        (vendor_app_id,),
    )
    if row is None or (connector_id and row["connector_id"] != connector_id):
        raise NotFoundError("Vendor app not found", code="vendor_app_not_found")
    return row


async def default_vendor_app(
    conn: Conn, connector_id: str, tier: str = "read"
) -> dict[str, Any] | None:
    return await fetch_one(
        conn,
        """select * from control.vendor_app where environment_id is null and connector_id = %s
             and is_default and config ->> 'permission_tier' = %s and deleted_at is null""",
        (connector_id, tier),
    )


async def resolve_vendor_app(conn: Conn, integration: dict[str, Any]) -> dict[str, Any] | None:
    if integration.get("vendor_app_id"):
        return await get_vendor_app_row(conn, integration["vendor_app_id"])
    tier = "read_write" if integration.get("write_back_enabled") else "read"
    return await default_vendor_app(
        conn, integration["connector_id"], tier
    ) or await default_vendor_app(conn, integration["connector_id"], "read")


async def create_vendor_app(
    platform: Platform,
    principal: Principal,
    *,
    connector_id: str,
    name: str,
    base_url: str,
    config: dict[str, Any],
    secrets: dict[str, Any],
    webhook_secret: str | None,
) -> dict[str, Any]:
    """A customer-owned app registration. Secrets are write-only."""
    principal.require("provisioning:write")
    manifest = platform.registry.manifest(connector_id)
    if manifest.auth.vendor_app == "none":
        raise ValidationFailedError(
            f"{manifest.id} does not use vendor apps", code="vendor_app_unsupported"
        )
    try:
        await check_url(
            base_url, allow_private=platform.settings.egress_allow_private, require_https=True
        )
    except EgressDenied as exc:
        raise ValidationFailedError(
            f"base_url rejected by the egress policy: {exc.message}",
            code="invalid_base_url",
            errors=[{"field": "base_url", "message": exc.message}],
        ) from exc
    from securefabric_core.ids import uuid7

    app_id = uuid7()
    async with tenant_tx(platform.pool, principal.env) as conn:
        sealed, version = await seal_for(
            conn, principal.env, connection_id=app_id, purpose="vendor_app", payload=secrets
        )
        ingress = None
        if webhook_secret:
            if platform.ingress is None:
                raise ValidationFailedError(
                    "INGRESS_KEY is not configured", code="ingress_unavailable"
                )
            ingress = platform.ingress.encrypt(webhook_secret.encode(), bound_to=str(app_id))
        row = await fetch_one(
            conn,
            """insert into control.vendor_app (id, environment_id, connector_id, name, base_url, config,
                 secrets_sealed, secrets_key_version, ingress_secret_enc)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning *""",
            (
                app_id,
                principal.env,
                manifest.id,
                name,
                base_url.rstrip("/"),
                json.dumps(config),
                sealed,
                version,
                ingress,
            ),
        )
        assert row is not None
        await audit(
            conn, principal, "vendor_app.created", target_kind="vendor_app", target_id=app_id
        )
    return vendor_app_out(row)


async def list_vendor_apps(platform: Platform, principal: Principal) -> list[dict[str, Any]]:
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        rows = await fetch_all(
            conn, "select * from control.vendor_app where deleted_at is null order by created_at"
        )
    return [vendor_app_out(r) for r in rows]


async def get_vendor_app(
    platform: Platform, principal: Principal, vendor_app_id: UUID
) -> dict[str, Any]:
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        return vendor_app_out(await get_vendor_app_row(conn, vendor_app_id))


async def update_vendor_app(
    platform: Platform,
    principal: Principal,
    vendor_app_id: UUID,
    *,
    name: str | None,
    config: dict[str, Any] | None,
    secrets: dict[str, Any] | None,
    webhook_secret: str | None,
) -> dict[str, Any]:
    principal.require("provisioning:write")
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await get_vendor_app_row(conn, vendor_app_id)
        if row["environment_id"] is None:
            raise NotFoundError(
                "Vendor app not found", code="vendor_app_not_found"
            )  # platform apps are read-only
        if name is not None:
            await conn.execute(
                "update control.vendor_app set name = %s where id = %s", (name, vendor_app_id)
            )
        if config is not None:
            await conn.execute(
                "update control.vendor_app set config = config || %s where id = %s",
                (json.dumps(config), vendor_app_id),
            )
        if secrets is not None:
            sealed, version = await seal_for(
                conn,
                principal.env,
                connection_id=vendor_app_id,
                purpose="vendor_app",
                payload=secrets,
            )
            await conn.execute(
                "update control.vendor_app set secrets_sealed = %s, secrets_key_version = %s where id = %s",
                (sealed, version, vendor_app_id),
            )
        if webhook_secret is not None and platform.ingress is not None:
            await conn.execute(
                "update control.vendor_app set ingress_secret_enc = %s where id = %s",
                (
                    platform.ingress.encrypt(webhook_secret.encode(), bound_to=str(vendor_app_id)),
                    vendor_app_id,
                ),
            )
        await audit(
            conn,
            principal,
            "vendor_app.updated",
            target_kind="vendor_app",
            target_id=vendor_app_id,
            detail={
                "secrets_rotated": secrets is not None,
                "webhook_secret_rotated": webhook_secret is not None,
            },
        )
        return vendor_app_out(await get_vendor_app_row(conn, vendor_app_id))


async def delete_vendor_app(platform: Platform, principal: Principal, vendor_app_id: UUID) -> None:
    principal.require("provisioning:write")
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await get_vendor_app_row(conn, vendor_app_id)
        if row["environment_id"] is None:
            raise NotFoundError("Vendor app not found", code="vendor_app_not_found")
        used = await fetch_one(
            conn,
            "select count(*) as n from control.integration where vendor_app_id = %s and deleted_at is null",
            (vendor_app_id,),
        )
        if used and used["n"]:
            raise ConflictError(
                "An integration still uses this vendor app.", code="vendor_app_in_use"
            )
        await conn.execute(
            "update control.vendor_app set deleted_at = now(), secrets_sealed = null where id = %s",
            (vendor_app_id,),
        )
        await audit(
            conn, principal, "vendor_app.deleted", target_kind="vendor_app", target_id=vendor_app_id
        )


# ---------------------------------------------------------------- platform app bootstrap


async def bootstrap_platform_apps(platform: Platform) -> list[dict[str, Any]]:
    """Register the platform-owned GitHub Apps from ``GITHUB_APP_*`` (part 9, section 5).
    Idempotent: re-running updates config and re-seals secrets."""
    s = platform.settings
    out: list[dict[str, Any]] = []
    specs = [
        (
            "read",
            s.github_app_id,
            s.github_app_slug,
            s.github_app_client_id,
            s.github_app_client_secret,
            s.github_app_webhook_secret,
            s.github_app_private_key_path,
            "SecureFabric (read)",
        ),
        (
            "read_write",
            s.github_app_rw_id,
            s.github_app_rw_slug,
            s.github_app_rw_client_id,
            s.github_app_rw_client_secret,
            s.github_app_rw_webhook_secret,
            s.github_app_rw_private_key_path,
            "SecureFabric (read and write)",
        ),
    ]
    async with system_tx(platform.sys_pool) as conn:
        for tier, app_id, slug, client_id, client_secret, hook_secret, key_path, label in specs:
            if not (app_id and slug and key_path):
                continue
            private_key = key_path.read_text(encoding="utf-8")
            base = s.github_app_base_url.rstrip("/")
            api_base = (
                "https://api.github.com" if base == "https://github.com" else f"{base}/api/v3"
            )
            config = {
                "app_id": str(app_id),
                "slug": slug,
                "client_id": client_id,
                "api_base_url": api_base,
                "permission_tier": tier,
            }
            row = await fetch_one(
                conn,
                """select * from control.vendor_app where environment_id is null and connector_id = 'GITHUB'
                     and is_default and config ->> 'permission_tier' = %s and deleted_at is null""",
                (tier,),
            )
            if row is None:
                row = await fetch_one(
                    conn,
                    """insert into control.vendor_app (environment_id, connector_id, name, base_url, config, is_default)
                       values (null, 'GITHUB', %s, %s, %s, true) returning *""",
                    (label, base, json.dumps(config)),
                )
                assert row is not None
            sealed = await seal_platform(
                conn,
                platform,
                purpose="vendor_app",
                owner_id=str(row["id"]),
                payload={
                    "private_key": private_key,
                    "client_secret": client_secret.get_secret_value() if client_secret else None,
                },
            )
            ingress = (
                platform.ingress.encrypt(
                    hook_secret.get_secret_value().encode(), bound_to=str(row["id"])
                )
                if hook_secret and platform.ingress
                else None
            )
            row = await fetch_one(
                conn,
                """update control.vendor_app set name = %s, base_url = %s, config = %s, secrets_sealed = %s,
                          ingress_secret_enc = coalesce(%s, ingress_secret_enc)
                    where id = %s returning *""",
                (label, base, json.dumps(config), sealed, ingress, row["id"]),
            )
            assert row is not None
            out.append(vendor_app_out(row))
            log.info(
                "platform_vendor_app_ready", tier=tier, vendor_app_id=str(row["id"]), slug=slug
            )
        # Apps that connectors ship themselves (Connector.platform_app; SANDBOX_OAUTH).
        for connector in platform.registry.all():
            reg = connector.platform_app()
            if reg is None:
                continue
            cid = connector.manifest.id
            config = {**reg["config"], "permission_tier": "read"}
            row = await default_vendor_app(conn, cid, "read")
            if row is None:
                row = await fetch_one(
                    conn,
                    """insert into control.vendor_app (environment_id, connector_id, name, base_url, config, is_default)
                       values (null, %s, %s, %s, %s, true) returning *""",
                    (cid, reg["name"], reg["base_url"], json.dumps(config)),
                )
                assert row is not None
            sealed = await seal_platform(
                conn,
                platform,
                purpose="vendor_app",
                owner_id=str(row["id"]),
                payload=reg.get("secrets") or {},
            )
            row = await fetch_one(
                conn,
                """update control.vendor_app set name = %s, base_url = %s, config = %s, secrets_sealed = %s
                    where id = %s returning *""",
                (reg["name"], reg["base_url"], json.dumps(config), sealed, row["id"]),
            )
            assert row is not None
            out.append(vendor_app_out(row))
            log.info("platform_vendor_app_ready", connector=cid, vendor_app_id=str(row["id"]))
    return out
