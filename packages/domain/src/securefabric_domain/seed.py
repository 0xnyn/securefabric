"""The demo workspace: a dev environment with sandbox connections and a production
environment with real-looking customers, each with a week of history.

Ported from the dash's ``seedWorkspace()``. Run ``make seed`` (``securefabric-seed``)
to (re)create it. The API also seeds an empty database on its first workspace read.
"""

import argparse
import asyncio
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from securefabric_db import DatabaseSettings
from securefabric_domain.catalog import provider_or_404
from securefabric_domain.models import ALL_KEY_SCOPES, HealthCode, KeyScope, SyncFrequency
from securefabric_domain.repository import Conn, fetch_one
from securefabric_domain.service import (
    DEFAULT_CALLBACK_URL,
    SANDBOX_DOMAIN,
    full_counts,
    key_prefix,
    key_preview,
    sha256,
)

MINUTE = timedelta(minutes=1)
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
FREQ: dict[SyncFrequency, timedelta] = {
    "15m": 15 * MINUTE,
    "1h": HOUR,
    "4h": 4 * HOUR,
    "12h": 12 * HOUR,
    "24h": DAY,
}
_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"
_SEED_LOCK = 0x5EC0_FAB1  # pg advisory lock: one seeder at a time

TABLES = (
    "operations",
    "sync_jobs",
    "connections",
    "integrations",
    "api_keys",
    "webhooks",
    "variables",
    "environments",
    "members",
    "workspace",
)


class Rng(random.Random):
    def rid(self, prefix: str, length: int = 10) -> str:
        return f"{prefix}_{''.join(self.choice(_CHARS) for _ in range(length))}"

    def secret(self, prefix: str, length: int = 32) -> str:
        return f"{prefix}{''.join(self.choice(_CHARS) for _ in range(length))}"

    def hex(self, length: int) -> str:
        return "".join(self.choice("0123456789abcdef") for _ in range(length))


@dataclass(frozen=True)
class IntegrationSeed:
    provider: str
    age_days: int
    frequency: SyncFrequency
    write_scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnSeed:
    customer: str
    domain: str
    email: str
    integration: str
    health: HealthCode = "HEALTHY"
    sandbox: bool = False
    tier: str | None = None


DEV_INTEGRATIONS = (
    IntegrationSeed("tenable", 150, "1h"),
    IntegrationSeed("qualys", 140, "4h"),
    IntegrationSeed("crowdstrike", 90, "15m", ("devices:isolate",)),
    IntegrationSeed("wiz", 60, "1h"),
    IntegrationSeed("okta", 30, "4h"),
    IntegrationSeed("snyk", 20, "4h"),
)
PROD_INTEGRATIONS = (
    IntegrationSeed("tenable", 120, "1h"),
    IntegrationSeed("qualys", 118, "4h"),
    IntegrationSeed("crowdstrike", 70, "15m", ("devices:isolate",)),
    IntegrationSeed("wiz", 50, "1h"),
    IntegrationSeed("okta", 25, "4h"),
    IntegrationSeed("snyk", 14, "4h"),
)


def _sandbox(provider: str, name: str) -> ConnSeed:
    return ConnSeed(
        customer=f"Sandbox · {name}",
        domain=SANDBOX_DOMAIN,
        email="you@securefabric.dev",
        integration=provider,
        sandbox=True,
    )


DEV_CONNECTIONS = (
    _sandbox("tenable", "Tenable"),
    _sandbox("qualys", "Qualys"),
    _sandbox("crowdstrike", "CrowdStrike"),
    _sandbox("wiz", "Wiz"),
    _sandbox("okta", "Okta"),
    ConnSeed(
        "Internal security lab",
        "lab.securefabric.dev",
        "secops@securefabric.dev",
        "crowdstrike",
        health="UNAUTHORIZED",
    ),
)
# (customer, domain, contact mailbox, integration, plan, health)
_PROD: tuple[tuple[str, str, str, str, str, HealthCode], ...] = (
    ("Northwind Health", "northwindhealth.com", "secops", "tenable", "enterprise", "HEALTHY"),
    ("Northwind Health", "northwindhealth.com", "secops", "crowdstrike", "enterprise", "HEALTHY"),
    ("Northwind Health", "northwindhealth.com", "it", "okta", "enterprise", "HEALTHY"),
    ("Globex", "globex.io", "vuln-mgmt", "qualys", "growth", "HEALTHY"),
    ("Globex", "globex.io", "cloud", "wiz", "growth", "HEALTHY"),
    ("Initech", "initech.com", "security", "tenable", "growth", "HEALTHY"),
    ("Initech", "initech.com", "appsec", "snyk", "growth", "RATE_LIMIT_EXCEEDED"),
    ("Umbrella Logistics", "umbrella-logistics.com", "soc", "crowdstrike", "enterprise", "HEALTHY"),
    ("Umbrella Logistics", "umbrella-logistics.com", "soc", "wiz", "enterprise", "HEALTHY"),
    ("Hooli", "hooli.xyz", "infosec", "qualys", "starter", "UNAUTHORIZED"),
    ("Stark Freight", "starkfreight.com", "it-sec", "okta", "starter", "HEALTHY"),
    ("Vandelay Imports", "vandelay.co", "security", "snyk", "growth", "HEALTHY"),
    ("Vandelay Imports", "vandelay.co", "security", "tenable", "growth", "HEALTHY"),
    ("Cyberdyne Systems", "cyberdyne.ai", "secops", "wiz", "enterprise", "VENDOR_SERVER_ERROR"),
)
PROD_CONNECTIONS = tuple(
    ConnSeed(name, domain, f"{mailbox}@{domain}", integration, health=health, tier=tier)
    for name, domain, mailbox, integration, tier, health in _PROD
)

API_PATHS = {
    "cloud-findings": "/v1/cloud-findings",
    "cloud-resources": "/v1/cloud-resources",
    "code-findings": "/v1/code-findings",
}

MEMBERS: tuple[tuple[str, str, str, int | None], ...] = (
    ("you@acmesecurity.com", "You", "Full access", 172),
    ("priya@acmesecurity.com", "Priya Raman", "Full access", 160),
    ("marcus@acmesecurity.com", "Marcus Osei", "Contributor", 80),
    ("support@acmesecurity.com", "Support rotation", "Support", 40),
    ("lena@acmesecurity.com", "Lena Fischer", "Contributor", None),
)


def api_path(model: str) -> str:
    return API_PATHS.get(model, f"/v1/{model}")


def masked_credentials(provider: str, rng: Rng) -> dict[str, str]:
    out: dict[str, str] = {}
    for field in provider_or_404(provider).fields:
        if field.options:
            out[field.key] = field.options[0]
        elif field.secret:
            out[field.key] = f"••••••••••••{rng.hex(4)}"
        else:
            out[field.key] = f"{rng.hex(6)}••••{rng.hex(4)}"
    return out


class Seeder:
    def __init__(self, conn: Conn, now: datetime) -> None:
        self.conn = conn
        self.now = now
        self.rng = Rng(f"securefabric-playground:{now.date().isoformat()}")

    async def op(self, env_id: str, connection: dict[str, Any], **fields: Any) -> None:
        await self.conn.execute(
            """
            insert into fabric.operations (
                id, environment_id, connection_id, integration_id, provider, customer,
                type, action, status, status_code, method, path, records, duration_ms, started_at
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                self.rng.rid("op", 14),
                env_id,
                connection["id"],
                connection["integration_id"],
                connection["provider"],
                connection["customer"],
                fields["type"],
                fields["action"],
                fields["status"],
                fields.get("status_code"),
                fields.get("method"),
                fields.get("path"),
                fields.get("records"),
                fields.get("duration_ms", self.rng.randint(40, 900)),
                fields["started_at"],
            ),
        )

    async def workspace(self) -> None:
        await self.conn.execute(
            """
            insert into fabric.workspace (
                id, team_name, team_plan, team_slug, user_name, user_email, seeded_at
            ) values (
                1, 'Acme Security', 'Growth', 'acme-security', 'You', 'you@acmesecurity.com', %s
            )
            """,
            (self.now,),
        )
        for email, name, role, age in MEMBERS:
            joined = self.now - age * DAY if age is not None else None
            await self.conn.execute(
                "insert into fabric.members (id, email, name, role, joined_at, created_at)"
                " values (%s, %s, %s, %s, %s, %s)",
                (self.rng.rid("usr"), email, name, role, joined, joined or self.now),
            )
        await self.environment(
            "dev", "Development", False, DEV_INTEGRATIONS, DEV_CONNECTIONS, volume=260
        )
        await self.environment(
            "prod", "Production", True, PROD_INTEGRATIONS, PROD_CONNECTIONS, volume=420
        )

    async def environment(
        self,
        slug: str,
        name: str,
        is_production: bool,
        integrations: tuple[IntegrationSeed, ...],
        connections: tuple[ConnSeed, ...],
        volume: int,
    ) -> None:
        rng, now = self.rng, self.now
        env_id = rng.rid("env")
        created = now - (170 if is_production else 172) * DAY
        prefix = key_prefix(is_production)
        secret = rng.secret(prefix)
        await self.conn.execute(
            """
            insert into fabric.environments (
                id, slug, name, is_production, callback_url, connect, default_key_secret,
                keys_rotated_at, webhook_secret, created_at
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                env_id,
                slug,
                name,
                is_production,
                DEFAULT_CALLBACK_URL,
                Jsonb({"brandName": "Acme Security", "hideBadge": False, "theme": "system"}),
                secret,
                now,
                rng.secret("whsec_"),
                created,
            ),
        )
        keys: list[tuple[str, str, list[KeyScope], str, datetime, datetime | None, bool]] = [
            ("Backend", secret, list(ALL_KEY_SCOPES), "You", created, now - 2 * MINUTE, True),
            (
                "Terraform",
                rng.secret(prefix),
                ["connections:write", "integrations:write", "webhooks:write", "keys:write"],
                "Priya Raman",
                now - 120 * DAY,
                now - 3 * HOUR,
                False,
            ),
            (
                "Risk dashboard" if is_production else "Audit export",
                rng.secret(prefix),
                ["data:read"],
                "Marcus Osei",
                now - 30 * DAY,
                now - 20 * HOUR if is_production else None,
                False,
            ),
        ]
        for key_name, value, scopes, by, at, used, default in keys:
            await self.conn.execute(
                """
                insert into fabric.api_keys (
                    id, environment_id, name, preview, secret_sha256, scopes, is_default,
                    created_by, created_at, last_used_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    rng.rid("key"), env_id, key_name, key_preview(value), sha256(value),
                    scopes, default, by, at, used,
                ),
            )  # fmt: skip

        variables = (
            [("TICKET_PROJECT", "SEC")]
            if is_production
            else [("TICKET_PROJECT", "SEC-DEV"), ("SLACK_ALERTS_CHANNEL", "#sec-alerts-dev")]
        )
        for i, (key, value) in enumerate(variables):
            await self.conn.execute(
                "insert into fabric.variables (environment_id, key, value, secret, created_at)"
                " values (%s, %s, %s, false, %s)",
                (env_id, key, value, created + i * MINUTE),
            )
        await self.conn.execute(
            "insert into fabric.webhooks (id, environment_id, url, events, created_at)"
            " values (%s, %s, %s, %s, %s)",
            (
                rng.rid("wh"),
                env_id,
                "https://api.acmesecurity.com/webhooks/securefabric"
                if is_production
                else "https://acme-dev.ngrok.app/webhooks/securefabric",
                [
                    "connection.create.succeeded",
                    "connection.sync.unauthorized",
                    "connection.sync.succeeded",
                    "connection.sync.failed",
                ],
                now - 60 * DAY,
            ),
        )

        frequency: dict[str, SyncFrequency] = {}
        models: dict[str, list[str]] = {}
        for seed in integrations:
            provider = provider_or_404(seed.provider)
            frequency[seed.provider] = seed.frequency
            models[seed.provider] = list(provider.models)
            await self.conn.execute(
                """
                insert into fabric.integrations (
                    environment_id, id, provider, display_name, models, sync_frequency,
                    write_scopes, allow_sandbox, created_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    env_id,
                    seed.provider,
                    seed.provider,
                    provider.name,
                    list(provider.models),
                    seed.frequency,
                    list(seed.write_scopes),
                    not is_production,
                    now - seed.age_days * DAY,
                ),
            )

        live: list[dict[str, Any]] = []
        for spec in connections:
            live.append(await self.connection(env_id, spec, frequency, models))

        healthy = [c for c in live if c["health"] != "UNAUTHORIZED"] or live
        week_ago_minutes = 7 * 24 * 60
        for _ in range(volume):
            conn = rng.choice(healthy)
            at = now - rng.randint(0, week_ago_minutes) * MINUTE
            roll = rng.random()
            conn_models = models[conn["integration_id"]]
            if roll < 0.86 and conn_models:
                model = rng.choice(conn_models)
                code = rng.choices([200, 400, 401, 404, 422, 429], weights=[95, 1, 1, 1.5, 1, 0.5])[
                    0
                ]
                await self.op(
                    env_id, conn, type="api", action=f"GET {api_path(model)}",
                    status="success" if code < 400 else "failed", started_at=at,
                    duration_ms=rng.randint(38, 420), method="GET", path=api_path(model),
                    records=rng.randint(20, 100) if code == 200 else 0, status_code=code,
                )  # fmt: skip
            elif roll < 0.95:
                await self.op(
                    env_id, conn, type="proxy",
                    action=f"proxy GET {provider_or_404(conn['provider']).name}",
                    status="success" if rng.random() < 0.95 else "failed", started_at=at,
                    duration_ms=rng.randint(120, 1600), method="GET", path="/v1/passthrough",
                    status_code=200,
                )  # fmt: skip
            else:
                writes = provider_or_404(conn["provider"]).write_actions
                if writes:
                    action = rng.choice(writes)
                    method, _, path = action.endpoint.partition(" ")
                    await self.op(
                        env_id, conn, type="action",
                        action=action.name.lower().replace(" ", "_"),
                        status="success" if rng.random() < 0.9 else "failed", started_at=at,
                        duration_ms=rng.randint(800, 6000), method=method, path=path,
                        status_code=202,
                    )  # fmt: skip

    async def connection(
        self,
        env_id: str,
        seed: ConnSeed,
        frequency: dict[str, SyncFrequency],
        models: dict[str, list[str]],
    ) -> dict[str, Any]:
        rng, now = self.rng, self.now
        conn_id = rng.rid("conn", 12)
        created = now - rng.randint(2, 160) * DAY - rng.randint(0, 23) * HOUR
        counts = full_counts(conn_id, models[seed.integration])  # type: ignore[arg-type]
        total = sum(counts.values())
        org_id = f"org_{rng.hex(8)}"
        tags = {"end_user_email": seed.email, "organization_id": org_id}
        if seed.tier:
            tags["plan"] = seed.tier

        # Job history, newest first: scheduled runs back to the initial sync.
        period = FREQ[frequency[seed.integration]]
        jobs: list[dict[str, Any]] = []
        t = now - rng.randint(1, max(2, int(period / MINUTE) - 1)) * MINUTE
        while t > created + period and len(jobs) < 24:
            failed = seed.health == "UNAUTHORIZED" and len(jobs) < 3
            jobs.append(
                {
                    "added": 0 if failed else rng.randint(0, max(1, total // 100)),
                    "deleted": 0 if failed else rng.randint(0, max(1, total // 250)),
                    "updated": 0 if failed else rng.randint(0, max(1, total // 33)),
                    "duration_ms": rng.randint(400, 1800) if failed else rng.randint(8, 240) * 1000,
                    "failure_reason": "401 Unauthorized: invalid_client" if failed else None,
                    "started_at": t,
                    "status": "FAILED" if failed else "SUCCESS",
                    "type": "ON_DEMAND" if rng.random() < 0.08 else "SCHEDULED",
                }
            )
            t -= period
        jobs.append(
            {
                "added": total,
                "deleted": 0,
                "updated": 0,
                "duration_ms": rng.randint(60, 900) * 1000,
                "failure_reason": None,
                "started_at": created + rng.randint(5, 40) * timedelta(seconds=1),
                "status": "SUCCESS",
                "type": "INITIAL",
            }
        )
        last_ok = next((j["started_at"] for j in jobs if j["status"] == "SUCCESS"), None)

        customer = {"email": seed.email, "endUserId": f"org_{rng.hex(8)}", "orgName": seed.customer}
        await self.conn.execute(
            """
            insert into fabric.connections (
                id, environment_id, integration_id, provider, customer, domain, sandbox, health,
                credentials, counts, tags, metadata, created_at, last_sync_at
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                conn_id,
                env_id,
                seed.integration,
                seed.integration,
                Jsonb(customer),
                seed.domain,
                seed.sandbox,
                seed.health,
                Jsonb({} if seed.sandbox else masked_credentials(seed.integration, rng)),
                Jsonb(counts),
                Jsonb(tags),
                Jsonb({"plan": seed.tier} if seed.tier else {}),
                created,
                last_ok,
            ),
        )
        for job in jobs:
            await self.conn.execute(
                """
                insert into fabric.sync_jobs (
                    id, connection_id, type, status, started_at, duration_ms, added, updated,
                    deleted, failure_reason
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    rng.rid("job"),
                    conn_id,
                    job["type"],
                    job["status"],
                    job["started_at"],
                    job["duration_ms"],
                    job["added"],
                    job["updated"],
                    job["deleted"],
                    job["failure_reason"],
                ),
            )

        row = {
            "id": conn_id,
            "integration_id": seed.integration,
            "provider": seed.integration,
            "customer": seed.customer,
            "health": seed.health,
        }
        await self.op(
            env_id, row, type="auth", action="connection.created", status="success",
            started_at=created, duration_ms=rng.randint(900, 4000),
        )  # fmt: skip
        for job in (j for j in jobs if j["started_at"] >= now - 7 * DAY):
            failed = job["status"] == "FAILED"
            await self.op(
                env_id, row, type="sync",
                action="sync.initial" if job["type"] == "INITIAL" else "sync.run",
                status="failed" if failed else "success", started_at=job["started_at"],
                duration_ms=job["duration_ms"], records=job["added"] + job["updated"],
            )  # fmt: skip
            await self.op(
                env_id, row, type="webhook",
                action=f"webhook.connection.sync.{'failed' if failed else 'succeeded'}",
                status="success",
                started_at=job["started_at"] + timedelta(milliseconds=job["duration_ms"] + 400),
                duration_ms=rng.randint(60, 300), method="POST", status_code=200,
            )  # fmt: skip
        if seed.health == "UNAUTHORIZED":
            await self.op(
                env_id, row, type="auth", action="connection.unauthorized", status="failed",
                started_at=now - rng.randint(1, 6) * HOUR,
            )  # fmt: skip
        return row


async def seed(conn: Conn, *, reset: bool = False, now: datetime | None = None) -> bool:
    """Seed the demo workspace. Returns False if one exists and ``reset`` is off."""
    async with conn.transaction():
        await conn.execute("select pg_advisory_xact_lock(%s)", (_SEED_LOCK,))
        existing = await fetch_one(conn, "select 1 from fabric.workspace where id = 1")
        if existing and not reset:
            return False
        if reset:
            for table in TABLES:
                await conn.execute(
                    sql.SQL("delete from {}").format(sql.Identifier("fabric", table))
                )
        await Seeder(conn, now or datetime.now(UTC)).workspace()
    return True


async def ensure_seeded(conn: Conn) -> None:
    if await fetch_one(conn, "select 1 from fabric.workspace where id = 1") is None:
        await seed(conn)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the SecureFabric demo workspace")
    parser.add_argument("--reset", action="store_true", help="wipe the control plane first")
    args = parser.parse_args()

    async def _run() -> None:
        url = DatabaseSettings().url
        async with await psycopg.AsyncConnection.connect(url, autocommit=True) as conn:
            created = await seed(conn, reset=args.reset)
        print("seeded the demo workspace" if created else "workspace already seeded (use --reset)")

    asyncio.run(_run())


if __name__ == "__main__":
    main()
