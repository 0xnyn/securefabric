"""Tenancy: principals, API keys, accounts, environments, organizations, audit.

docs/plan/03-tenancy-connections-vault.md, sections 1-4.
"""

import json
import re
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import errors as pg_errors
from psycopg import sql

from securefabric_core import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    UnauthenticatedError,
    ValidationFailedError,
)
from securefabric_core.crypto import generate_key_pair, keyed_hash, random_base62
from securefabric_core.ids import uuid7
from securefabric_db import Conn, fetch_all, fetch_one, set_tenant, tenant_tx
from securefabric_domain.paging import PageOut, clamp_limit, keyset_page
from securefabric_domain.runtime import Platform

SCOPES: tuple[str, ...] = (
    "provisioning:read",
    "provisioning:write",
    "data:read",
    "jobs:execute",
    "webhooks:manage",
    "keys:manage",
    "actions:write",
)
ALL_SCOPES = frozenset(SCOPES)

ROLE_SCOPES: dict[str, frozenset[str]] = {
    "admin": ALL_SCOPES,
    "developer": ALL_SCOPES - {"keys:manage"},
    "support": frozenset({"provisioning:read", "data:read"}),
}

KEY_PATTERN = re.compile(r"^sfk_(live|test)_([a-z0-9]{2,8})_([A-Za-z0-9]{43})$")
KEY_CACHE_TTL_S = 30.0  # revocation takes effect within 60 s (TEN-06)


@dataclass(frozen=True)
class Principal:
    """Both authenticators produce this. Nothing below the API knows which was used."""

    kind: str  # api_key | user | connect_session | system
    account_id: UUID | None
    environment_id: UUID | None
    scopes: frozenset[str]
    actor_id: str
    role: str | None = None
    is_operator: bool = False
    organization_id: UUID | None = None  # connect sessions are scoped to one
    request_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def env(self) -> UUID:
        if self.environment_id is None:
            raise BadRequestError(
                "Select an environment with the X-Environment-Id header.",
                code="environment_required",
            )
        return self.environment_id

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise PermissionDeniedError(
                f"This credential lacks {scope}.", code="scope_missing", scope=scope
            )

    def require_admin(self) -> None:
        if self.kind == "user" and self.role != "admin":
            raise PermissionDeniedError(
                "Only admins can do this.", code="role_required", role="admin"
            )

    def with_request(
        self, *, request_id: str | None, ip: str | None, user_agent: str | None
    ) -> "Principal":
        return replace(self, request_id=request_id, ip=ip, user_agent=user_agent)


SYSTEM = Principal(
    kind="system", account_id=None, environment_id=None, scopes=ALL_SCOPES, actor_id="system"
)


def system_principal(environment_id: UUID, account_id: UUID | None = None) -> Principal:
    return replace(SYSTEM, environment_id=environment_id, account_id=account_id)


# ---------------------------------------------------------------- audit (SEC-08)


async def audit(
    conn: Conn,
    principal: Principal,
    action: str,
    *,
    target_kind: str | None = None,
    target_id: object = None,
    detail: dict[str, Any] | None = None,
    environment_id: UUID | None = None,
) -> None:
    actor_kind = {"api_key": "api_key", "user": "user", "connect_session": "connect_session"}.get(
        principal.kind, "system"
    )
    if principal.kind == "user" and principal.extra.get("support"):
        actor_kind = "support"
    await conn.execute(
        """
        insert into obs.audit_event (environment_id, account_id, actor_kind, actor_id, action,
                                     target_kind, target_id, ip, user_agent, request_id, detail)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            environment_id or principal.environment_id,
            principal.account_id,
            actor_kind,
            principal.actor_id,
            action,
            target_kind,
            str(target_id) if target_id is not None else None,
            principal.ip,
            principal.user_agent,
            principal.request_id,
            json.dumps(detail or {}, default=str),
        ),
    )


# ---------------------------------------------------------------- API keys


def generate_api_key(*, is_production: bool, region: str) -> tuple[str, str]:
    """``sfk_<live|test>_<region>_<43 base62>`` (~256 bits). Returns (key, prefix)."""
    env = "live" if is_production else "test"
    key = f"sfk_{env}_{region}_{random_base62(43)}"
    return key, key[: len(f"sfk_{env}_{region}_") + 4]


def hash_api_key(pepper: bytes, key: str) -> bytes:
    return keyed_hash(pepper, key)


class _KeyCache:
    def __init__(self) -> None:
        self._entries: dict[bytes, tuple[float, Principal | None]] = {}

    def get(self, h: bytes) -> tuple[bool, Principal | None]:
        hit = self._entries.get(h)
        if hit is None or time.monotonic() - hit[0] > KEY_CACHE_TTL_S:
            return False, None
        return True, hit[1]

    def put(self, h: bytes, principal: Principal | None) -> None:
        if len(self._entries) > 10_000:
            self._entries.clear()
        self._entries[h] = (time.monotonic(), principal)

    def clear(self) -> None:
        self._entries.clear()


KEY_CACHE = _KeyCache()


async def authenticate_api_key(platform: Platform, raw: str) -> Principal:
    m = KEY_PATTERN.match(raw.strip())
    if not m:
        raise UnauthenticatedError("The API key is malformed.", code="invalid_api_key")
    if m.group(2) != platform.region:
        # API-10: a key from another region is rejected before any lookup.
        raise UnauthenticatedError(
            f"This key belongs to region {m.group(2)!r}; this API serves {platform.region!r}.",
            code="wrong_region",
        )
    h = hash_api_key(platform.pepper, raw.strip())
    cached, principal = KEY_CACHE.get(h)
    if not cached:
        async with platform.pool.connection() as conn:
            row = await fetch_one(conn, "select * from control.resolve_api_key(%s)", (h,))
        principal = None
        now = platform.clock.now()
        if (
            row
            and row["revoked_at"] is None
            and (row["expires_at"] is None or row["expires_at"] > now)
        ):
            principal = Principal(
                kind="api_key",
                account_id=row["account_id"],
                environment_id=row["environment_id"],
                scopes=frozenset(row["scopes"]),
                actor_id=str(row["id"]),
                extra={"key_name": row["name"], "is_production": row["is_production"]},
            )
            await _touch_key(platform, row["id"], row["environment_id"])
        KEY_CACHE.put(h, principal)
    if principal is None:
        raise UnauthenticatedError(
            "The API key is invalid, expired or revoked.", code="invalid_api_key"
        )
    return principal


async def _touch_key(platform: Platform, key_id: UUID, environment_id: UUID) -> None:
    # last_used_at is updated at most once a minute per key.
    async with tenant_tx(platform.pool, environment_id) as conn:
        await conn.execute(
            """update control.api_key set last_used_at = now()
                where id = %s and (last_used_at is null or last_used_at < now() - interval '1 minute')""",
            (key_id,),
        )


def _key_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        k: row[k]
        for k in (
            "id",
            "name",
            "prefix",
            "scopes",
            "created_at",
            "last_used_at",
            "expires_at",
            "revoked_at",
            "created_by",
        )
    }


async def create_api_key(
    platform: Platform,
    principal: Principal,
    *,
    name: str,
    scopes: list[str] | None,
    expires_at: datetime | None = None,
) -> tuple[dict[str, Any], str]:
    principal.require("keys:manage")
    chosen = list(dict.fromkeys(scopes or SCOPES))
    unknown = [s for s in chosen if s not in ALL_SCOPES]
    if unknown:
        raise ValidationFailedError(
            f"Unknown scopes: {unknown}",
            code="invalid_scopes",
            errors=[{"field": "scopes", "message": f"unknown: {unknown}"}],
        )
    if principal.kind == "api_key":
        # A key cannot mint a key with more power than itself.
        extra = [s for s in chosen if s not in principal.scopes]
        if extra:
            raise PermissionDeniedError(
                f"Cannot grant scopes this key lacks: {extra}", code="scope_escalation"
            )
    env = principal.env
    async with tenant_tx(platform.pool, env) as conn:
        e = await fetch_one(
            conn, "select is_production from control.environment where id = %s", (env,)
        )
        if e is None:
            raise NotFoundError("Environment not found", code="environment_not_found")
        key, prefix = generate_api_key(is_production=e["is_production"], region=platform.region)
        row = await fetch_one(
            conn,
            """insert into control.api_key (environment_id, name, prefix, hash, scopes, created_by, expires_at)
               values (%s, %s, %s, %s, %s, %s, %s) returning *""",
            (
                env,
                name,
                prefix,
                hash_api_key(platform.pepper, key),
                chosen,
                _actor_uuid(principal),
                expires_at,
            ),
        )
        assert row is not None
        await audit(
            conn,
            principal,
            "api_key.created",
            target_kind="api_key",
            target_id=row["id"],
            detail={"name": name, "scopes": chosen},
        )
    return _key_out(row), key


def _actor_uuid(principal: Principal) -> UUID | None:
    try:
        return UUID(principal.actor_id)
    except ValueError:
        return None


async def list_api_keys(platform: Platform, principal: Principal) -> list[dict[str, Any]]:
    principal.require("keys:manage")
    async with tenant_tx(platform.pool, principal.env) as conn:
        rows = await fetch_all(conn, "select * from control.api_key order by created_at desc")
    return [_key_out(r) for r in rows]


async def revoke_api_key(platform: Platform, principal: Principal, key_id: UUID) -> dict[str, Any]:
    principal.require("keys:manage")
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await fetch_one(
            conn,
            "update control.api_key set revoked_at = coalesce(revoked_at, now()) where id = %s returning *",
            (key_id,),
        )
        if row is None:
            raise NotFoundError("API key not found", code="api_key_not_found")
        await audit(conn, principal, "api_key.revoked", target_kind="api_key", target_id=key_id)
    KEY_CACHE.clear()  # this process forgets at once; others within the 30 s TTL
    return _key_out(row)


# ---------------------------------------------------------------- accounts and environments

SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:40] or "account"


async def upsert_user(
    conn: Conn, *, workos_user_id: str, email: str, name: str | None
) -> dict[str, Any]:
    row = await fetch_one(
        conn,
        """insert into control.app_user (workos_user_id, email, name, last_seen_at)
           values (%s, %s, %s, now())
           on conflict (workos_user_id) do update
              set email = excluded.email, name = coalesce(excluded.name, control.app_user.name),
                  last_seen_at = now()
           returning *""",
        (workos_user_id, email, name),
    )
    assert row is not None
    return row


async def create_environment_row(
    platform: Platform,
    conn: Conn,
    *,
    account_id: UUID,
    slug: str,
    name: str,
    is_production: bool,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not SLUG.match(slug):
        raise ValidationFailedError("Invalid environment slug", code="invalid_slug")
    env_id = uuid7()
    pair = generate_key_pair(platform.kek)
    await set_tenant(conn, env_id)
    try:
        await conn.execute(
            """insert into control.environment (id, account_id, slug, name, is_production, settings,
                                                vault_public_key, vault_private_key_wrapped)
               values (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                env_id,
                account_id,
                slug,
                name,
                is_production,
                json.dumps(settings or default_environment_settings()),
                pair.public_key,
                pair.private_key_wrapped,
            ),
        )
    except pg_errors.UniqueViolation as exc:
        raise ConflictError(
            f"An environment named {slug!r} already exists.", code="environment_exists"
        ) from exc
    return {
        "id": env_id,
        "account_id": account_id,
        "slug": slug,
        "name": name,
        "is_production": is_production,
    }


def default_environment_settings() -> dict[str, Any]:
    return {
        "connect_ui": {
            "name": None,
            "logo_url": None,
            "accent_color": "#4f46e5",
            "theme": "system",
        },
        "allowed_redirect_origins": [],
        "default_sync_interval_s": 3600,
    }


async def provision_account(
    platform: Platform,
    *,
    name: str,
    workos_organization_id: str | None,
    admin_user_id: UUID | None,
    slug: str | None = None,
) -> dict[str, Any]:
    """A new account gets an admin membership and two environments, dev and prod."""
    async with platform.pool.connection() as conn, conn.transaction():
        base = slug or slugify(name)
        candidate = base
        for i in range(1, 50):
            exists = await fetch_one(
                conn, "select 1 from control.account where slug = %s", (candidate,)
            )
            if not exists:
                break
            candidate = f"{base}-{i + 1}"
        account = await fetch_one(
            conn,
            """insert into control.account (name, slug, workos_organization_id)
               values (%s, %s, %s) returning *""",
            (name, candidate, workos_organization_id),
        )
        assert account is not None
        if admin_user_id is not None:
            await conn.execute(
                "insert into control.membership (account_id, user_id, role) values (%s, %s, 'admin')"
                " on conflict do nothing",
                (account["id"], admin_user_id),
            )
        envs = []
        for slug_, label, prod in (("dev", "Development", False), ("prod", "Production", True)):
            envs.append(
                await create_environment_row(
                    platform,
                    conn,
                    account_id=account["id"],
                    slug=slug_,
                    name=label,
                    is_production=prod,
                )
            )
        principal = Principal(
            kind="user" if admin_user_id else "system",
            account_id=account["id"],
            environment_id=None,
            scopes=ALL_SCOPES,
            actor_id=str(admin_user_id or "system"),
        )
        await audit(
            conn,
            principal,
            "account.created",
            target_kind="account",
            target_id=account["id"],
            detail={"name": name},
        )
    return {**account, "environments": envs}


async def account_environments(platform: Platform, account_id: UUID) -> list[dict[str, Any]]:
    async with platform.pool.connection() as conn:
        return await fetch_all(
            conn, "select * from control.account_environments(%s)", (account_id,)
        )


async def resolve_environment(platform: Platform, account_id: UUID, ref: str) -> dict[str, Any]:
    """An ``X-Environment-Id`` header value (uuid or slug) that must belong to the account."""
    for env in await account_environments(platform, account_id):
        if str(env["id"]) == ref or env["slug"] == ref:
            return env
    raise NotFoundError("Environment not found", code="environment_not_found")


async def create_environment(
    platform: Platform, principal: Principal, *, slug: str, name: str, is_production: bool
) -> dict[str, Any]:
    principal.require_admin()
    if principal.account_id is None:
        raise PermissionDeniedError("No account", code="account_required")
    async with platform.pool.connection() as conn, conn.transaction():
        env = await create_environment_row(
            platform,
            conn,
            account_id=principal.account_id,
            slug=slug,
            name=name,
            is_production=is_production,
        )
        await audit(
            conn,
            principal,
            "environment.created",
            target_kind="environment",
            target_id=env["id"],
            environment_id=env["id"],
        )
    return env


async def update_environment_settings(
    platform: Platform, principal: Principal, settings: dict[str, Any], name: str | None = None
) -> dict[str, Any]:
    principal.require_admin()
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await fetch_one(
            conn,
            """update control.environment set settings = settings || %s, name = coalesce(%s, name)
                where id = %s
            returning id, account_id, slug, name, is_production, settings, created_at""",
            (json.dumps(settings), name, principal.env),
        )
        if row is None:
            raise NotFoundError("Environment not found", code="environment_not_found")
        await audit(
            conn,
            principal,
            "environment.updated",
            target_kind="environment",
            target_id=principal.env,
            detail={"keys": sorted(settings)},
        )
    return row


async def get_environment(conn: Conn, environment_id: UUID) -> dict[str, Any]:
    row = await fetch_one(
        conn,
        """select id, account_id, slug, name, is_production, settings, vault_public_key,
                  vault_key_version, created_at
             from control.environment where id = %s and deleted_at is null""",
        (environment_id,),
    )
    if row is None:
        raise NotFoundError("Environment not found", code="environment_not_found")
    return row


# ---------------------------------------------------------------- organizations (TEN-03, TEN-04)


def _org_out(row: dict[str, Any]) -> dict[str, Any]:
    out = {k: row[k] for k in ("id", "identifier", "name", "metadata", "created_at", "updated_at")}
    if "connection_count" in row:
        out["connection_count"] = row["connection_count"]
    return out


async def create_organization(
    platform: Platform,
    principal: Principal,
    *,
    identifier: str,
    name: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    principal.require("provisioning:write")
    async with tenant_tx(platform.pool, principal.env) as conn:
        try:
            row = await fetch_one(
                conn,
                """insert into control.organization (environment_id, identifier, name, metadata)
                   values (%s, %s, %s, %s) returning *""",
                (principal.env, identifier, name, json.dumps(metadata or {})),
            )
        except pg_errors.UniqueViolation as exc:
            raise ConflictError(
                f"An organization with identifier {identifier!r} already exists.",
                code="organization_exists",
            ) from exc
        assert row is not None
        await audit(
            conn, principal, "organization.created", target_kind="organization", target_id=row["id"]
        )
    return {**_org_out(row), "connection_count": 0}


async def get_organization(conn: Conn, organization_id: UUID) -> dict[str, Any]:
    row = await fetch_one(
        conn,
        """select o.*, (select count(*) from control.connection c
                         where c.organization_id = o.id and c.deleted_at is null) as connection_count
             from control.organization o where o.id = %s and o.deleted_at is null""",
        (organization_id,),
    )
    if row is None:
        raise NotFoundError("Organization not found", code="organization_not_found")
    return _org_out(row)


async def read_organization(
    platform: Platform, principal: Principal, organization_id: UUID
) -> dict[str, Any]:
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        return await get_organization(conn, organization_id)


async def list_organizations(
    platform: Platform,
    principal: Principal,
    *,
    name: str | None = None,
    identifier: str | None = None,
    ids: list[UUID] | None = None,
    search: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> PageOut[dict[str, Any]]:
    principal.require("provisioning:read")
    where: list[sql.Composable] = [sql.SQL("o.deleted_at is null")]
    params: list[Any] = []
    if name:
        where.append(sql.SQL("o.name = %s"))
        params.append(name)
    if identifier:
        where.append(sql.SQL("o.identifier = %s"))
        params.append(identifier)
    if ids:
        where.append(sql.SQL("o.id = any(%s)"))
        params.append(ids)
    if search:
        where.append(sql.SQL("(o.name ilike %s or o.identifier ilike %s)"))
        like = f"%{search.replace('%', r'\%').replace('_', r'\_')}%"
        params.extend([like, like])
    filters = {
        "name": name,
        "identifier": identifier,
        "ids": [str(i) for i in ids or []],
        "search": search,
    }
    async with tenant_tx(platform.pool, principal.env) as conn:
        page = await keyset_page(
            conn,
            key=platform.cursor_key,
            base=sql.SQL("""select o.*, (select count(*) from control.connection c
                                         where c.organization_id = o.id and c.deleted_at is null)
                                     as connection_count from control.organization o"""),
            where=where,
            params=params,
            sort_name="created_at:asc",
            sort_exprs=["o.created_at", "o.id"],
            sort_keys=lambda r: [r["created_at"], str(r["id"])],
            descending=False,
            cursor_token=cursor,
            filters=filters,
            scope=f"orgs:{principal.env}",
            limit=clamp_limit(limit),
        )
    return PageOut([_org_out(r) for r in page.items], page.next_cursor, page.previous_cursor)


async def update_organization(
    platform: Platform,
    principal: Principal,
    organization_id: UUID,
    *,
    name: str | None,
    identifier: str | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    principal.require("provisioning:write")
    async with tenant_tx(platform.pool, principal.env) as conn:
        try:
            row = await fetch_one(
                conn,
                """update control.organization
                      set name = coalesce(%s, name), identifier = coalesce(%s, identifier),
                          metadata = coalesce(%s, metadata), updated_at = now()
                    where id = %s and deleted_at is null returning id""",
                (
                    name,
                    identifier,
                    json.dumps(metadata) if metadata is not None else None,
                    organization_id,
                ),
            )
        except pg_errors.UniqueViolation as exc:
            raise ConflictError(
                "Another organization already uses that identifier.", code="organization_exists"
            ) from exc
        if row is None:
            raise NotFoundError("Organization not found", code="organization_not_found")
        await audit(
            conn,
            principal,
            "organization.updated",
            target_kind="organization",
            target_id=organization_id,
        )
        return await get_organization(conn, organization_id)


async def delete_organization(
    platform: Platform, principal: Principal, organization_id: UUID
) -> None:
    """409 while the organization has a PENDING, ACTIVE or PAUSED connection (TEN-03)."""
    principal.require("provisioning:write")
    async with tenant_tx(platform.pool, principal.env) as conn:
        org = await fetch_one(
            conn,
            "select id from control.organization where id = %s and deleted_at is null for update",
            (organization_id,),
        )
        if org is None:
            raise NotFoundError("Organization not found", code="organization_not_found")
        live = await fetch_one(
            conn,
            """select count(*) as n from control.connection where organization_id = %s
                and state in ('PENDING', 'ACTIVE', 'PAUSED')""",
            (organization_id,),
        )
        if live and live["n"]:
            raise ConflictError(
                f"The organization has {live['n']} live connection(s). Delete them first.",
                code="organization_has_connections",
            )
        await conn.execute(
            "update control.organization set deleted_at = now() where id = %s", (organization_id,)
        )
        await audit(
            conn,
            principal,
            "organization.deleted",
            target_kind="organization",
            target_id=organization_id,
        )
