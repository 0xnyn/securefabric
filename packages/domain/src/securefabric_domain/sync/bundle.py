"""Everything a slice needs about one connection, and the connector Context."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx2

from securefabric_cdk.connector import Connector
from securefabric_cdk.context import Context
from securefabric_cdk.fixtures import ReplayTransport, load_fixtures
from securefabric_cdk.http import HttpClient, OpLog, RateBudget, RawCapture
from securefabric_cdk.manifest import Manifest, validate_options
from securefabric_core import NotFoundError
from securefabric_core.clock import Clock
from securefabric_db import Conn, fetch_one
from securefabric_domain.catalog import resolve_vendor_app
from securefabric_domain.runtime import Platform
from securefabric_domain.sync.credentials import build_auth
from securefabric_domain.sync.ratebudget import DbRateBudget


@dataclass
class Bundle:
    connection: dict[str, Any]
    integration: dict[str, Any]
    vendor_app: dict[str, Any] | None
    connector: Connector
    options: dict[str, Any]

    @property
    def manifest(self) -> Manifest:
        return self.connector.manifest

    @property
    def config(self) -> dict[str, Any]:
        cfg: dict[str, Any] = dict(self.connection["connection_config"] or {})
        if self.vendor_app is not None:
            cfg.setdefault("vendor_app_id", str(self.vendor_app["id"]))
        return cfg

    @property
    def environment_id(self) -> UUID:
        env: UUID = self.connection["environment_id"]
        return env

    @property
    def connection_id(self) -> UUID:
        cid: UUID = self.connection["id"]
        return cid

    def budget_key(self) -> str:
        template = self.manifest.http.budget.key
        values = {
            "connection_id": str(self.connection_id),
            **{k: str(v) for k, v in self.config.items()},
            "vendor_app_id": str(self.vendor_app["id"]) if self.vendor_app else "none",
        }
        try:
            key = template.format(**values)
        except (KeyError, IndexError):
            key = str(self.connection_id)
        return f"{self.manifest.id}:{key}" if not key.startswith(self.manifest.id) else key


def merged_options(
    connector: Connector, integration: dict[str, Any], connection: dict[str, Any]
) -> dict[str, Any]:
    raw = {**(integration.get("option_defaults") or {}), **(connection.get("options") or {})}
    try:
        return validate_options(connector.manifest, raw)
    except Exception:
        # Stored options were valid when written; a manifest change must not crash reads.
        return raw


async def load_bundle(platform: Platform, conn: Conn, connection_id: UUID) -> Bundle:
    row = await fetch_one(conn, "select * from control.connection where id = %s", (connection_id,))
    if row is None:
        raise NotFoundError("Connection not found", code="connection_not_found")
    integration = await fetch_one(
        conn, "select * from control.integration where id = %s", (row["integration_id"],)
    )
    assert integration is not None
    connector = platform.registry.get(row["connector_id"])
    vendor_app = None
    if connector.manifest.auth.vendor_app != "none":
        vendor_app = await resolve_vendor_app(conn, integration)
    return Bundle(
        connection=row,
        integration=integration,
        vendor_app=vendor_app,
        connector=connector,
        options=merged_options(connector, integration, row),
    )


def fixtures_transport(connector: Connector) -> httpx2.AsyncBaseTransport:
    """A sandbox connection of a real connector replays its recorded fixtures (TEN-13)."""
    base: Path = connector.package_dir() / "fixtures"
    files = sorted(f for f in base.rglob("*.json") if f.name != "connection.json")
    return ReplayTransport(load_fixtures(files), strict=False)


async def build_context(
    platform: Platform,
    bundle: Bundle,
    *,
    stream: str | None,
    op_log: OpLog,
    capture: RawCapture | None,
    clock: Clock,
    interactive: bool,
    deadline: datetime | None = None,
    budget: RateBudget | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
    credentials_override: dict[str, Any] | None = None,
) -> Context:
    connector = bundle.connector
    config = bundle.config
    if transport is None:
        transport = connector.local_transport(config, bundle.options)
    if transport is None and bundle.connection.get("is_sandbox"):
        transport = fixtures_transport(connector)
    if transport is None:
        transport = platform.vendor_transport()
    spec = bundle.manifest.http
    if budget is None:
        budget = DbRateBudget(
            platform.pool,
            bundle.budget_key(),
            per_hour=spec.budget.per_hour,
            per_second=spec.budget.max_requests_per_second,
            clock=clock,
            sleep=platform.sleep,
        )
    http = HttpClient(
        base_url=connector.base_url(config, bundle.vendor_app),
        transport=transport,
        spec=spec,
        budget=budget,
        capture=capture,
        log=op_log,
        clock=clock,
        sleep=platform.sleep,
        scrub_fields=bundle.manifest.scrub_fields,
        interactive=interactive,
        stream=stream,
        connector=bundle.manifest.id,
    )
    if (
        bundle.connection.get("is_sandbox")
        and connector.local_transport(config, bundle.options) is None
    ):
        # A sandbox connection of a real connector replays recorded fixtures (TEN-13): no
        # credentials exist and nothing may reach the vendor, so every scheme gets a
        # placeholder the replay transport ignores.
        from securefabric_cdk.tokens import StaticSecret

        http._auth = StaticSecret({"Authorization": "Bearer sandbox-replay"})
    else:
        http._auth = await build_auth(
            platform,
            connector,
            environment_id=bundle.environment_id,
            connection_id=bundle.connection_id,
            vendor_app=bundle.vendor_app,
            config=config,
            http=http,
            clock=clock,
            credentials_override=credentials_override,
        )
    return Context(
        http=http,
        config=config,
        options=bundle.options,
        clock=clock,
        deadline=deadline,
        stream=stream,
        log_sink=op_log,
    )


async def budget_key_for(platform: Platform, conn: Conn, connection_id: UUID) -> str:
    return (await load_bundle(platform, conn, connection_id)).budget_key()
