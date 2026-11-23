"""Writes: every operation the dash performs, as a Postgres transaction.

Ported from the dash's former in-browser store (``apps/dash/src/lib/store.ts``),
so behaviour matches what the UI was designed around: operations are logged the
same way, webhooks "fire" for subscribed events, and syncs move a connection
through ``SYNCING`` → ``HEALTHY``.

Syncs are split in two. :func:`start_sync` records a RUNNING job here, and the
caller spawns a durable ``sync-connection`` task. The worker then calls
:func:`finish_sync` when the (simulated) vendor sync completes.
"""

import hashlib
import random
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import quote

from psycopg import sql
from psycopg.types.json import Jsonb

from securefabric_core import ConflictError, NotFoundError, ValidationFailedError
from securefabric_domain.catalog import get_catalog, provider_or_404
from securefabric_domain.models import (
    ALL_KEY_SCOPES,
    ApiKeyCreate,
    ApiKeyPatch,
    ApiKeySecret,
    ConnectionCreate,
    ConnectionPatch,
    ConnectSession,
    ConnectSessionCreate,
    EnvironmentCreate,
    EnvironmentPatch,
    HealthCode,
    IntegrationCreate,
    IntegrationPatch,
    JobType,
    MemberInvite,
    MemberPatch,
    ModelKey,
    OperationCreate,
    OperationStatus,
    OperationType,
    Role,
    VariableSet,
    WebhookCreate,
    WebhookDelivery,
    WebhookEvent,
    WebhookPatch,
)
from securefabric_domain.repository import (
    Conn,
    Row,
    api_key_model,
    connection_row,
    environment_row,
    fetch_all,
    fetch_one,
    from_ms,
    integration_row,
    make_id,
    make_secret,
)

SANDBOX_DOMAIN = "sandbox.securefabric.dev"
DEFAULT_CALLBACK_URL = "https://api.securefabric.dev/v1/connect/callback"
CONNECT_URL = "https://connect.securefabric.dev/s"

# How long the simulated vendor sync takes, as the dash's old timers did.
INITIAL_SYNC_SECONDS = 4.2
ON_DEMAND_SYNC_SECONDS = 2.6

# Record counts per model for a connection of typical size (min, max).
_COUNT_RANGES: dict[str, tuple[int, int]] = {
    "alerts": (40, 180),
    "cloud-findings": (120, 900),
    "cloud-resources": (400, 3200),
    "code-findings": (80, 640),
    "detections": (12, 90),
    "devices": (140, 2400),
    "groups": (12, 12),
    "repositories": (12, 12),
    "tickets": (30, 400),
    "users": (80, 1800),
    "vulnerabilities": (800, 14_000),
}
_SLUG_CHARS = re.compile(r"[^a-z0-9-]+")


def now() -> datetime:
    return datetime.now(UTC)


def key_preview(key: str) -> str:
    """What's kept of a key after it's shown once: the prefix and last four."""
    return f"{key[:7]}…{key[-4:]}"


def key_prefix(is_production: bool) -> str:
    return "sk_live_" if is_production else "sk_test_"


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def mask_value(value: str) -> str:
    return "••••" if len(value) <= 4 else f"••••••••••••{value[-4:]}"


def record_count(seed: str, model: str) -> int:
    lo, hi = _COUNT_RANGES.get(model, (10, 50))
    return random.Random(f"{seed}:{model}:count").randint(lo, hi)  # noqa: S311


def full_counts(seed: str, models: list[ModelKey]) -> dict[str, int]:
    return {m: record_count(seed, m) for m in models}


def slugify(name: str) -> str:
    return _SLUG_CHARS.sub("", name.strip().lower().replace(" ", "-"))[:24].strip("-")


def unique_key(base: str, taken: set[str]) -> str:
    """``base``, or ``base-2``, ``base-3``... whichever is free."""
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def masked_credentials(provider_slug: str, values: Mapping[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for field in provider_or_404(provider_slug).fields:
        value = values.get(field.key, "")
        out[field.key] = mask_value(value) if field.secret else value
    return out


# --- Operations (logs) -------------------------------------------------------------


async def log(
    conn: Conn,
    env_id: str,
    connection: Row | None,
    *,
    type: OperationType,
    action: str,
    status: OperationStatus,
    duration_ms: int,
    started_at: datetime | None = None,
    method: str | None = None,
    path: str | None = None,
    records: int | None = None,
    status_code: int | None = None,
) -> str:
    op_id = make_id("op", 14)
    await conn.execute(
        """
        insert into fabric.operations (
            id, environment_id, connection_id, integration_id, provider, customer,
            type, action, status, status_code, method, path, records, duration_ms, started_at
        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            op_id,
            env_id,
            connection["id"] if connection else None,
            connection["integration_id"] if connection else None,
            connection["provider"] if connection else None,
            connection["customer"]["orgName"] if connection else None,
            type,
            action,
            status,
            status_code,
            method,
            path,
            records,
            duration_ms,
            started_at or now(),
        ),
    )
    return op_id


async def has_event(conn: Conn, env_id: str, event: WebhookEvent) -> bool:
    row = await fetch_one(
        conn,
        "select 1 from fabric.webhooks where environment_id = %s"
        " and not disabled and %s = any(events) limit 1",
        (env_id, event),
    )
    return row is not None


async def _fire(
    conn: Conn, env_id: str, connection: Row | None, event: WebhookEvent, at: datetime
) -> None:
    """Record the delivery of ``event`` if any endpoint subscribes to it."""
    if await has_event(conn, env_id, event):
        await log(
            conn,
            env_id,
            connection,
            type="webhook",
            action=f"webhook.{event}",
            status="success",
            duration_ms=random.randint(60, 300),  # noqa: S311
            method="POST",
            status_code=200,
            started_at=at,
        )


async def record_operation(conn: Conn, slug: str, body: OperationCreate) -> str:
    env = await environment_row(conn, slug)
    connection = (
        await connection_row(conn, env["id"], body.connection_id) if body.connection_id else None
    )
    return await log(
        conn,
        env["id"],
        connection,
        type=body.type,
        action=body.action,
        status=body.status,
        duration_ms=body.duration_ms,
        method=body.method,
        path=body.path,
        records=body.records,
        status_code=body.status_code,
        started_at=from_ms(body.started_at) if body.started_at else None,
    )


# --- Environments -------------------------------------------------------------------


async def insert_environment(
    conn: Conn,
    *,
    slug: str,
    name: str,
    is_production: bool,
    created_by: str,
    created_at: datetime | None = None,
    connect: Mapping[str, Any] | None = None,
) -> str:
    """A blank environment with its default key (every scope)."""
    env_id = make_id("env")
    secret = make_secret(key_prefix(is_production))
    created = created_at or now()
    await conn.execute(
        """
        insert into fabric.environments (
            id, slug, name, is_production, callback_url, connect,
            default_key_secret, keys_rotated_at, webhook_secret, created_at
        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            env_id,
            slug,
            name,
            is_production,
            DEFAULT_CALLBACK_URL,
            Jsonb(
                dict(
                    connect or {"brandName": "Acme Security", "hideBadge": False, "theme": "system"}
                )
            ),
            secret,
            created,
            make_secret("whsec_"),
            created,
        ),
    )
    await conn.execute(
        """
        insert into fabric.api_keys (
            id, environment_id, name, preview, secret_sha256, scopes, is_default,
            created_by, created_at
        ) values (%s, %s, 'Default', %s, %s, %s, true, %s, %s)
        """,
        (
            make_id("key"),
            env_id,
            key_preview(secret),
            sha256(secret),
            list(ALL_KEY_SCOPES),
            created_by,
            created,
        ),
    )
    return env_id


async def _user_name(conn: Conn) -> str:
    row = await fetch_one(conn, "select user_name from fabric.workspace where id = 1")
    return row["user_name"] if row else "You"


async def create_environment(conn: Conn, body: EnvironmentCreate) -> str:
    async with conn.transaction():
        taken = {r["slug"] for r in await fetch_all(conn, "select slug from fabric.environments")}
        slug = unique_key(slugify(body.slug or body.name) or "env", taken)
        source = (
            await fetch_one(
                conn, "select * from fabric.environments where slug = %s", (body.copy_from,)
            )
            if body.copy_from
            else None
        )
        env_id = await insert_environment(
            conn,
            slug=slug,
            name=body.name,
            is_production=body.is_production,
            created_by=await _user_name(conn),
            connect=source["connect"] if source else None,
        )
        if source:
            await conn.execute(
                """
                insert into fabric.integrations (
                    environment_id, id, provider, display_name, models, sync_frequency,
                    write_scopes, allow_sandbox
                )
                select %s, id, provider, display_name, models, sync_frequency, write_scopes,
                       case when %s then false else allow_sandbox end
                from fabric.integrations where environment_id = %s
                """,
                (env_id, body.is_production, source["id"]),
            )
            await conn.execute(
                """
                insert into fabric.variables (environment_id, key, value, secret)
                select %s, key, value, secret from fabric.variables where environment_id = %s
                """,
                (env_id, source["id"]),
            )
    return slug


async def update_environment(conn: Conn, slug: str, patch: EnvironmentPatch) -> None:
    async with conn.transaction():
        env = await environment_row(conn, slug)
        connect = dict(env["connect"])
        if patch.connect is not None:
            connect.update(patch.connect.model_dump(by_alias=True, exclude_none=True))
        await conn.execute(
            """
            update fabric.environments set
                name = coalesce(%s, name),
                is_production = coalesce(%s, is_production),
                callback_url = coalesce(%s, callback_url),
                connect = %s
            where id = %s
            """,
            (patch.name, patch.is_production, patch.callback_url, Jsonb(connect), env["id"]),
        )


async def delete_environment(conn: Conn, slug: str) -> None:
    async with conn.transaction():
        env = await environment_row(conn, slug)
        count = await fetch_one(conn, "select count(*) as n from fabric.environments")
        if count and count["n"] <= 1:
            raise ConflictError("A workspace keeps at least one environment", environment=slug)
        await conn.execute("delete from fabric.environments where id = %s", (env["id"],))


# --- API keys ------------------------------------------------------------------------


async def create_api_key(conn: Conn, slug: str, body: ApiKeyCreate) -> ApiKeySecret:
    async with conn.transaction():
        env = await environment_row(conn, slug)
        secret = make_secret(key_prefix(env["is_production"]))
        row = await fetch_one(
            conn,
            """
            insert into fabric.api_keys (
                id, environment_id, name, preview, secret_sha256, scopes, created_by
            ) values (%s, %s, %s, %s, %s, %s, %s)
            returning *
            """,
            (
                make_id("key"),
                env["id"],
                body.name,
                key_preview(secret),
                sha256(secret),
                list(dict.fromkeys(body.scopes)),
                await _user_name(conn),
            ),
        )
        assert row is not None  # noqa: S101 (INSERT ... RETURNING always returns)
        return ApiKeySecret(key=api_key_model(row), secret=secret)


async def _api_key_row(conn: Conn, env_id: str, key_id: str) -> Row:
    row = await fetch_one(
        conn,
        "select * from fabric.api_keys where environment_id = %s and id = %s",
        (env_id, key_id),
    )
    if row is None:
        raise NotFoundError("API key not found", key=key_id)
    return row


async def update_api_key(conn: Conn, slug: str, key_id: str, patch: ApiKeyPatch) -> None:
    async with conn.transaction():
        env = await environment_row(conn, slug)
        await _api_key_row(conn, env["id"], key_id)
        await conn.execute(
            "update fabric.api_keys set name = coalesce(%s, name),"
            " scopes = coalesce(%s, scopes) where id = %s",
            (patch.name, list(dict.fromkeys(patch.scopes)) if patch.scopes else None, key_id),
        )


async def roll_api_key(conn: Conn, slug: str, key_id: str) -> ApiKeySecret:
    """Replace a key's value. Rolling the default key changes the dash's samples too."""
    async with conn.transaction():
        env = await environment_row(conn, slug)
        target = await _api_key_row(conn, env["id"], key_id)
        secret = make_secret(key_prefix(env["is_production"]))
        row = await fetch_one(
            conn,
            "update fabric.api_keys set preview = %s, secret_sha256 = %s where id = %s returning *",
            (key_preview(secret), sha256(secret), key_id),
        )
        assert row is not None  # noqa: S101
        if target["is_default"]:
            await conn.execute(
                "update fabric.environments set default_key_secret = %s, keys_rotated_at = now()"
                " where id = %s",
                (secret, env["id"]),
            )
        return ApiKeySecret(key=api_key_model(row), secret=secret)


async def revoke_api_key(conn: Conn, slug: str, key_id: str) -> None:
    async with conn.transaction():
        env = await environment_row(conn, slug)
        target = await _api_key_row(conn, env["id"], key_id)
        if target["is_default"]:
            raise ConflictError("The default key can be rolled but not revoked", key=key_id)
        await conn.execute("delete from fabric.api_keys where id = %s", (key_id,))


# --- Webhooks and variables ------------------------------------------------------------


async def rotate_webhook_secret(conn: Conn, slug: str) -> None:
    env = await environment_row(conn, slug)
    await conn.execute(
        "update fabric.environments set webhook_secret = %s where id = %s",
        (make_secret("whsec_"), env["id"]),
    )


async def add_webhook(conn: Conn, slug: str, body: WebhookCreate) -> str:
    env = await environment_row(conn, slug)
    hook_id = make_id("wh")
    await conn.execute(
        "insert into fabric.webhooks (id, environment_id, url, description, events)"
        " values (%s, %s, %s, %s, %s)",
        (hook_id, env["id"], body.url, body.description, list(dict.fromkeys(body.events))),
    )
    return hook_id


async def _webhook_row(conn: Conn, env_id: str, hook_id: str) -> Row:
    row = await fetch_one(
        conn,
        "select * from fabric.webhooks where environment_id = %s and id = %s",
        (env_id, hook_id),
    )
    if row is None:
        raise NotFoundError("Webhook endpoint not found", webhook=hook_id)
    return row


async def update_webhook(conn: Conn, slug: str, hook_id: str, patch: WebhookPatch) -> None:
    env = await environment_row(conn, slug)
    await _webhook_row(conn, env["id"], hook_id)
    await conn.execute(
        """
        update fabric.webhooks set
            url = coalesce(%s, url),
            events = coalesce(%s, events),
            description = coalesce(%s, description),
            disabled = coalesce(%s, disabled)
        where id = %s
        """,
        (
            patch.url,
            list(dict.fromkeys(patch.events)) if patch.events else None,
            patch.description,
            patch.disabled,
            hook_id,
        ),
    )


async def remove_webhook(conn: Conn, slug: str, hook_id: str) -> None:
    env = await environment_row(conn, slug)
    await _webhook_row(conn, env["id"], hook_id)
    await conn.execute("delete from fabric.webhooks where id = %s", (hook_id,))


async def deliver_webhook(conn: Conn, slug: str, hook_id: str, body: WebhookDelivery) -> str:
    """Deliver one event to one endpoint now: a test event, or a resend."""
    env = await environment_row(conn, slug)
    hook = await _webhook_row(conn, env["id"], hook_id)
    connection = (
        await connection_row(conn, env["id"], body.connection_id) if body.connection_id else None
    )
    return await log(
        conn,
        env["id"],
        connection,
        type="webhook",
        action=f"webhook.{body.event}",
        status="success",
        duration_ms=random.randint(120, 380),  # noqa: S311
        method="POST",
        path=hook["url"],
        status_code=200,
    )


async def set_variable(conn: Conn, slug: str, key: str, body: VariableSet) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", key):
        raise ValidationFailedError("Variable names are letters, digits and underscores", key=key)
    env = await environment_row(conn, slug)
    await conn.execute(
        """
        insert into fabric.variables (environment_id, key, value, secret) values (%s, %s, %s, %s)
        on conflict (environment_id, key)
        do update set value = excluded.value, secret = excluded.secret
        """,
        (env["id"], key, body.value, body.secret),
    )


async def remove_variable(conn: Conn, slug: str, key: str) -> None:
    env = await environment_row(conn, slug)
    await conn.execute(
        "delete from fabric.variables where environment_id = %s and key = %s", (env["id"], key)
    )


# --- Integrations ----------------------------------------------------------------------


def _check_models(provider_slug: str, models: list[ModelKey]) -> None:
    offered = set(provider_or_404(provider_slug).models)
    unknown = [m for m in models if m not in offered]
    if unknown:
        raise ValidationFailedError(
            "The provider doesn't offer these models", provider=provider_slug, models=unknown
        )


async def enable_integration(conn: Conn, slug: str, body: IntegrationCreate) -> str:
    provider = provider_or_404(body.provider)
    models = body.models if body.models is not None else list(provider.models)
    _check_models(provider.slug, models)
    async with conn.transaction():
        env = await environment_row(conn, slug)
        taken = {
            r["id"]
            for r in await fetch_all(
                conn, "select id from fabric.integrations where environment_id = %s", (env["id"],)
            )
        }
        integration_id = unique_key(body.id or provider.slug, taken)
        await conn.execute(
            """
            insert into fabric.integrations (
                environment_id, id, provider, display_name, models, sync_frequency,
                write_scopes, allow_sandbox
            ) values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                env["id"],
                integration_id,
                provider.slug,
                body.display_name or provider.name,
                list(models),
                body.sync_frequency,
                body.write_scopes,
                body.allow_sandbox if body.allow_sandbox is not None else not env["is_production"],
            ),
        )
    return integration_id


async def update_integration(
    conn: Conn, slug: str, integration_id: str, patch: IntegrationPatch
) -> str:
    """Returns the integration's (possibly renamed) key. Connections follow a rename."""
    async with conn.transaction():
        env = await environment_row(conn, slug)
        current = await integration_row(conn, env["id"], integration_id)
        if patch.models is not None:
            _check_models(current["provider"], patch.models)
        new_id = patch.id or integration_id
        if new_id != integration_id:
            clash = await fetch_one(
                conn,
                "select 1 from fabric.integrations where environment_id = %s and id = %s",
                (env["id"], new_id),
            )
            if clash:
                raise ConflictError("That integration key is taken", integration=new_id)
        await conn.execute(
            """
            update fabric.integrations set
                id = %s,
                display_name = coalesce(%s, display_name),
                models = coalesce(%s, models),
                sync_frequency = coalesce(%s, sync_frequency),
                write_scopes = coalesce(%s, write_scopes),
                allow_sandbox = coalesce(%s, allow_sandbox)
            where environment_id = %s and id = %s
            """,
            (
                new_id,
                patch.display_name,
                list(patch.models) if patch.models is not None else None,
                patch.sync_frequency,
                patch.write_scopes,
                patch.allow_sandbox,
                env["id"],
                integration_id,
            ),
        )
    return new_id


async def delete_integration(conn: Conn, slug: str, integration_id: str) -> None:
    async with conn.transaction():
        env = await environment_row(conn, slug)
        await integration_row(conn, env["id"], integration_id)
        await conn.execute(
            "delete from fabric.integrations where environment_id = %s and id = %s",
            (env["id"], integration_id),
        )


# --- Connections and syncs ----------------------------------------------------------------


async def start_sync(conn: Conn, connection_id: str, job_type: JobType) -> str:
    """Record a RUNNING job and mark the connection SYNCING. Call inside a transaction."""
    job_id = make_id("job")
    await conn.execute(
        "insert into fabric.sync_jobs (id, connection_id, type, status)"
        " values (%s, %s, %s, 'RUNNING')",
        (job_id, connection_id, job_type),
    )
    await conn.execute(
        "update fabric.connections set health = 'SYNCING' where id = %s", (connection_id,)
    )
    return job_id


async def attach_task(conn: Conn, job_id: str, task_id: str) -> None:
    await conn.execute("update fabric.sync_jobs set task_id = %s where id = %s", (task_id, job_id))


async def create_connection(conn: Conn, slug: str, body: ConnectionCreate) -> tuple[str, str]:
    """Create a connection and start its initial sync. Returns (connection_id, job_id)."""
    async with conn.transaction():
        env = await environment_row(conn, slug)
        integration = await integration_row(conn, env["id"], body.integration_id)
        if body.sandbox and not integration["allow_sandbox"]:
            raise ValidationFailedError(
                "Sandbox connections are off for this integration", integration=integration["id"]
            )
        connection_id = make_id("conn", 12)
        customer = body.customer.model_dump(by_alias=True)
        domain = (
            SANDBOX_DOMAIN
            if body.sandbox
            else (
                body.customer.email.split("@")[1] if "@" in body.customer.email else "example.com"
            )
        )
        await conn.execute(
            """
            insert into fabric.connections (
                id, environment_id, integration_id, provider, customer, domain, sandbox,
                health, credentials, tags
            ) values (%s, %s, %s, %s, %s, %s, %s, 'SYNCING', %s, %s)
            """,
            (
                connection_id,
                env["id"],
                integration["id"],
                integration["provider"],
                Jsonb(customer),
                domain,
                body.sandbox,
                Jsonb(
                    {}
                    if body.sandbox
                    else masked_credentials(integration["provider"], body.credentials)
                ),
                Jsonb(
                    {
                        "end_user_email": body.customer.email,
                        "end_user_id": body.customer.end_user_id,
                        **body.tags,
                    }
                ),
            ),
        )
        job_id = await start_sync(conn, connection_id, "INITIAL")
        row = await connection_row(conn, env["id"], connection_id)
        await log(
            conn,
            env["id"],
            row,
            type="auth",
            action="connection.created (sandbox)" if body.sandbox else "connection.created",
            status="success",
            duration_ms=210 if body.sandbox else 1840,
        )
        await _fire(conn, env["id"], row, "connection.create.succeeded", now())
    return connection_id, job_id


async def trigger_sync(
    conn: Conn, slug: str, connection_id: str
) -> tuple[str, Literal["started", "failed"]]:
    """Start an on-demand sync. Unauthorized connections fail at once, as the vendor would."""
    async with conn.transaction():
        env = await environment_row(conn, slug)
        row = await connection_row(conn, env["id"], connection_id)
        running = await fetch_one(
            conn,
            "select id from fabric.sync_jobs where connection_id = %s and status = 'RUNNING'"
            " order by started_at desc limit 1",
            (connection_id,),
        )
        if running:
            raise ConflictError("A sync is already running", job=running["id"])
        if row["health"] == "UNAUTHORIZED":
            job_id = make_id("job")
            await conn.execute(
                """
                insert into fabric.sync_jobs (
                    id, connection_id, type, status, duration_ms, failure_reason
                ) values (%s, %s, 'ON_DEMAND', 'FAILED', 612, %s)
                """,
                (
                    job_id,
                    connection_id,
                    "401 Unauthorized: the vendor rejected the stored credentials",
                ),
            )
            await log(
                conn,
                env["id"],
                row,
                type="sync",
                action="sync.run",
                status="failed",
                duration_ms=612,
            )
            await _fire(conn, env["id"], row, "connection.sync.unauthorized", now())
            return job_id, "failed"
        return await start_sync(conn, connection_id, "ON_DEMAND"), "started"


async def finish_sync(conn: Conn, connection_id: str, job_id: str) -> dict[str, Any]:
    """Complete a RUNNING job (called by the worker). Idempotent: replays are no-ops."""
    async with conn.transaction():
        job = await fetch_one(
            conn, "select * from fabric.sync_jobs where id = %s for update", (job_id,)
        )
        row = await fetch_one(
            conn, "select * from fabric.connections where id = %s for update", (connection_id,)
        )
        if job is None or row is None or job["status"] != "RUNNING":
            return {"status": "skipped", "jobId": job_id}

        integration = await fetch_one(
            conn,
            "select models from fabric.integrations where environment_id = %s and id = %s",
            (row["environment_id"], row["integration_id"]),
        )
        models: list[ModelKey] = (
            integration["models"] if integration else list(provider_or_404(row["provider"]).models)
        )
        rng = random.Random(f"{job_id}:finish")  # noqa: S311
        initial = job["type"] == "INITIAL"
        counts: dict[str, int] = full_counts(connection_id, models) if initial else row["counts"]
        total = sum(counts.values())
        added = total if initial else rng.randint(0, max(1, total // 100))
        updated = 0 if initial else rng.randint(0, max(1, total // 50))
        deleted = 0 if initial else rng.randint(0, max(1, total // 300))
        finished_at = now()
        duration_ms = int((finished_at - job["started_at"]).total_seconds() * 1000)

        await conn.execute(
            """
            update fabric.sync_jobs set status = 'SUCCESS', duration_ms = %s,
                added = %s, updated = %s, deleted = %s
            where id = %s
            """,
            (duration_ms, added, updated, deleted, job_id),
        )
        await conn.execute(
            "update fabric.connections set counts = %s, health = %s, last_sync_at = %s"
            " where id = %s",
            (
                Jsonb(counts),
                "PAUSED" if row["paused"] else "HEALTHY",
                finished_at,
                connection_id,
            ),
        )
        await log(
            conn,
            row["environment_id"],
            row,
            type="sync",
            action="sync.initial" if initial else "sync.run",
            status="success",
            duration_ms=duration_ms,
            records=added + updated,
            started_at=job["started_at"],
        )
        await _fire(
            conn,
            row["environment_id"],
            row,
            "connection.sync.succeeded",
            finished_at + timedelta(milliseconds=300),
        )
    return {
        "status": "SUCCESS",
        "jobId": job_id,
        "added": added,
        "updated": updated,
        "deleted": deleted,
    }


async def fail_sync(conn: Conn, connection_id: str, job_id: str, reason: str) -> None:
    """Mark a RUNNING job failed (the worker gave up on it)."""
    async with conn.transaction():
        job = await fetch_one(
            conn, "select * from fabric.sync_jobs where id = %s for update", (job_id,)
        )
        row = await fetch_one(
            conn, "select * from fabric.connections where id = %s", (connection_id,)
        )
        if job is None or row is None or job["status"] != "RUNNING":
            return
        await conn.execute(
            "update fabric.sync_jobs set status = 'FAILED', failure_reason = %s,"
            " duration_ms = (extract(epoch from now() - started_at) * 1000)::int where id = %s",
            (reason, job_id),
        )
        await conn.execute(
            "update fabric.connections set health = 'VENDOR_SERVER_ERROR' where id = %s",
            (connection_id,),
        )
        await log(
            conn,
            row["environment_id"],
            row,
            type="sync",
            action="sync.run",
            status="failed",
            duration_ms=0,
        )
        await _fire(conn, row["environment_id"], row, "connection.sync.failed", now())


async def update_connection(
    conn: Conn, slug: str, connection_id: str, patch: ConnectionPatch
) -> None:
    fields = patch.model_fields_set
    async with conn.transaction():
        env = await environment_row(conn, slug)
        row = await connection_row(conn, env["id"], connection_id)
        sets: list[sql.Composable] = []
        params: list[Any] = []
        if "paused" in fields and patch.paused is not None:
            sets += [sql.SQL("paused = %s"), sql.SQL("health = %s")]
            params += [patch.paused, "PAUSED" if patch.paused else "HEALTHY"]
        if "frequency_override" in fields:
            sets.append(sql.SQL("frequency_override = %s"))
            params.append(patch.frequency_override)
        if "webhook_override" in fields:
            sets.append(sql.SQL("webhook_override = %s"))
            params.append(patch.webhook_override or None)
        for name in ("tags", "metadata"):
            value = getattr(patch, name)
            if name in fields and value is not None:
                sets.append(sql.SQL("{} = %s").format(sql.Identifier(name)))
                params.append(Jsonb(value))
        if not sets:
            return
        params.append(row["id"])
        await conn.execute(
            sql.SQL("update fabric.connections set {} where id = %s").format(
                sql.SQL(", ").join(sets)
            ),
            params,
        )


async def update_credentials(
    conn: Conn, slug: str, connection_id: str, values: Mapping[str, str]
) -> str:
    """Store new (masked) credentials, mark healthy and re-sync. Returns the job id."""
    async with conn.transaction():
        env = await environment_row(conn, slug)
        row = await connection_row(conn, env["id"], connection_id)
        await conn.execute(
            "update fabric.connections set credentials = %s, health = 'HEALTHY' where id = %s",
            (Jsonb(masked_credentials(row["provider"], values)), connection_id),
        )
        await log(
            conn,
            env["id"],
            row,
            type="auth",
            action="connection.credentials_updated",
            status="success",
            duration_ms=1320,
        )
        return await start_sync(conn, connection_id, "ON_DEMAND")


async def delete_connection(conn: Conn, slug: str, connection_id: str) -> None:
    async with conn.transaction():
        env = await environment_row(conn, slug)
        row = await connection_row(conn, env["id"], connection_id)
        await log(
            conn,
            env["id"],
            row,
            type="auth",
            action="connection.deleted",
            status="success",
            duration_ms=96,
        )
        await _fire(conn, env["id"], row, "connection.deleted", now())
        await conn.execute("delete from fabric.connections where id = %s", (connection_id,))


async def simulate_health(conn: Conn, slug: str, connection_id: str, health: HealthCode) -> None:
    """Simulate a vendor-side change, e.g. a customer revoking credentials."""
    async with conn.transaction():
        env = await environment_row(conn, slug)
        row = await connection_row(conn, env["id"], connection_id)
        await conn.execute(
            "update fabric.connections set health = %s where id = %s", (health, connection_id)
        )
        if health == "UNAUTHORIZED":
            await log(
                conn,
                env["id"],
                row,
                type="auth",
                action="connection.unauthorized",
                status="failed",
                duration_ms=540,
            )
            await _fire(conn, env["id"], row, "connection.sync.unauthorized", now())


async def create_connect_session(
    conn: Conn, slug: str, body: ConnectSessionCreate
) -> ConnectSession:
    env = await environment_row(conn, slug)
    token = make_secret("cs_", 40)
    scope = ", ".join(body.integrations) if body.integrations else "all integrations"
    await log(
        conn,
        env["id"],
        None,
        type="auth",
        action=f"connect_session.created ({scope})",
        status="success",
        duration_ms=64,
        method="POST",
        path="/v1/connect/sessions",
        status_code=201,
    )
    expires = now() + timedelta(minutes=30)
    return ConnectSession(
        expires_at=int(expires.timestamp() * 1000),
        token=token,
        url=f"{CONNECT_URL}/{token[3:23]}?org={quote(body.customer.end_user_id)}",
    )


# --- Team -----------------------------------------------------------------------------------


async def invite_member(conn: Conn, body: MemberInvite) -> str:
    exists = await fetch_one(conn, "select 1 from fabric.members where email = %s", (body.email,))
    if exists:
        raise ConflictError("Already a member", email=body.email)
    member_id = make_id("usr")
    await conn.execute(
        "insert into fabric.members (id, email, name, role) values (%s, %s, %s, %s)",
        (member_id, body.email, body.email.split("@")[0], body.role),
    )
    return member_id


async def _member_row(conn: Conn, member_id: str) -> Row:
    row = await fetch_one(conn, "select * from fabric.members where id = %s", (member_id,))
    if row is None:
        raise NotFoundError("Member not found", member=member_id)
    return row


async def set_member_role(conn: Conn, member_id: str, body: MemberPatch) -> None:
    await _member_row(conn, member_id)
    role: Role = body.role
    await conn.execute("update fabric.members set role = %s where id = %s", (role, member_id))


async def remove_member(conn: Conn, member_id: str) -> None:
    await _member_row(conn, member_id)
    await conn.execute("delete from fabric.members where id = %s", (member_id,))


def known_models() -> set[str]:
    return set(get_catalog().models)
