"""The in-process harness (M2): run one stream to completion against Postgres.

Uses the real executor and write path with no scheduler or Absurd, so connector
conformance, engine scenarios and the data API can be tested before (and
independently of) the queue.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx2
from pydantic import SecretStr

from securefabric_core.clock import Clock, FrozenClock
from securefabric_core.platform import PlatformSettings
from securefabric_db import DatabaseSettings, fetch_one, tenant_tx
from securefabric_domain.blob import MemoryBlobStore
from securefabric_domain.catalog import ensure_default_integration
from securefabric_domain.registry import ConnectorRegistry, default_registry
from securefabric_domain.runtime import Platform, Role, build_platform
from securefabric_domain.sync.executor import SliceInput, SliceOutcome, run_slice
from securefabric_domain.sync.oplog import start_operation
from securefabric_domain.tenancy import provision_account
from securefabric_domain.vault import seal_for
from securefabric_schema import Mode

TEST_KEYS = {
    "vault_master_key": SecretStr("dGVzdC1tYXN0ZXIta2V5LTMyLWJ5dGVzLWxvbmchISE="),
    "ingress_key": SecretStr("dGVzdC1pbmdyZXNzLWtleS0zMi1ieXRlcy1sb25nISE="),
    "api_key_pepper": SecretStr("dGVzdC1wZXBwZXIta2V5LTMyLWJ5dGVzLWxvbmchISE="),
    "cursor_signing_key": SecretStr("dGVzdC1jdXJzb3Ita2V5LTMyLWJ5dGVzLWxvbmchISE="),
}


def build_test_settings(**overrides: Any) -> PlatformSettings:
    values: dict[str, Any] = {
        **TEST_KEYS,
        "region": "us",
        "blob_endpoint": None,
        "workos_client_id": None,
        "workos_api_key": None,
        "github_app_id": None,
    }
    values.update(overrides)
    return PlatformSettings(_env_file=None, **values)


def build_test_platform(
    database_url: str,
    *,
    role: Role = "test",
    clock: Clock | None = None,
    registry: ConnectorRegistry | None = None,
    settings: PlatformSettings | None = None,
) -> Platform:
    clock = clock or FrozenClock()
    p = build_platform(
        role,
        settings=settings or build_test_settings(),
        db=DatabaseSettings(url=database_url, pool_min_size=0, pool_max_size=8),
        clock=clock,
        registry=registry or default_registry(),
        blob=MemoryBlobStore(),
    )
    if isinstance(clock, FrozenClock):

        async def advance(seconds: float) -> None:
            clock.advance(seconds)

        p.sleep = advance  # sleeping moves the test clock instead of waiting
    return p


@dataclass
class Tenant:
    account_id: UUID
    environment_id: UUID
    other_environment_id: UUID
    organization_id: UUID


async def make_tenant(platform: Platform, *, name: str | None = None) -> Tenant:
    account = await provision_account(
        platform,
        name=name or f"Acme {uuid.uuid4().hex[:6]}",
        workos_organization_id=None,
        admin_user_id=None,
    )
    dev, prod = account["environments"]
    async with tenant_tx(platform.pool, dev["id"]) as conn:
        org = await fetch_one(
            conn,
            "insert into control.organization (environment_id, identifier, name) values (%s, %s, %s) returning id",
            (dev["id"], f"org-{uuid.uuid4().hex[:6]}", "Customer One"),
        )
    assert org is not None
    return Tenant(account["id"], dev["id"], prod["id"], org["id"])


async def make_connection(
    platform: Platform,
    tenant: Tenant,
    connector_id: str = "SANDBOX",
    *,
    credentials: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    state: str = "ACTIVE",
    is_sandbox: bool = False,
    organization_id: UUID | None = None,
) -> UUID:
    """A connection inserted directly (the lifecycle service is exercised elsewhere)."""
    connector = platform.registry.get(connector_id)
    env = tenant.environment_id
    async with tenant_tx(platform.pool, env) as conn:
        integ = await ensure_default_integration(platform, conn, env, connector_id)
        cid = uuid.uuid4()
        await conn.execute(
            """insert into control.connection (id, environment_id, organization_id, integration_id, connector_id,
                     connector_version, state, options, connection_config, is_sandbox, health_status, health_code)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'INITIALIZING', 'INITIALIZING')""",
            (
                cid,
                env,
                organization_id or tenant.organization_id,
                integ["id"],
                connector.manifest.id,
                connector.manifest.version,
                state,
                json.dumps(options or {}),
                json.dumps(config or {}),
                is_sandbox,
            ),
        )
        sealed = None
        version = 1
        if credentials:
            sealed, version = await seal_for(
                conn, env, connection_id=cid, purpose="credential", payload=credentials
            )
        await conn.execute(
            """insert into control.credential (connection_id, environment_id, auth_mode, sealed, vault_key_version,
                                               fields_set) values (%s, %s, %s, %s, %s, %s)""",
            (
                cid,
                env,
                connector.manifest.auth.mode.value,
                sealed,
                version,
                sorted((credentials or {}).keys()),
            ),
        )
    return cid


async def sync_stream(
    platform: Platform,
    tenant: Tenant,
    connection_id: UUID,
    stream: str,
    mode: Mode = Mode.FULL,
    *,
    generation: int | None = None,
    max_pages: int | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
    target_keys: list[str] | None = None,
) -> SliceOutcome:
    op = await start_operation(
        platform.pool,
        environment_id=tenant.environment_id,
        kind="sync",
        action=f"harness:{stream}",
        connection_id=connection_id,
    )
    return await run_slice(
        platform,
        SliceInput(
            environment_id=tenant.environment_id,
            connection_id=connection_id,
            stream=stream,
            mode=mode,
            generation=generation,
            max_pages=max_pages,
            target_keys=target_keys,
        ),
        op_log=op,
        transport=transport,
    )


async def rows(
    platform: Platform,
    tenant: Tenant,
    connection_id: UUID,
    table: str = "data.vulnerability_finding",
    *,
    include_deleted: bool = True,
) -> list[dict[str, Any]]:
    from securefabric_db import fetch_all

    where = "" if include_deleted else " and deleted_at is null"
    async with tenant_tx(platform.pool, tenant.environment_id) as conn:
        return await fetch_all(
            conn,
            f"select * from {table} where connection_id = %s{where} order by natural_key",  # noqa: S608
            (connection_id,),
        )


# ---------------------------------------------------------------- engine driver (M3)


class EngineDriver:
    """Runs scheduler ticks and executes the Absurd tasks they admit, in-process.

    The same handler the worker registers is called for each claimed task, so
    scenario tests exercise admission, Absurd leases and outcome handling exactly
    as deployed, without sleeping: the clock is advanced instead.
    """

    def __init__(self, platform: Platform) -> None:
        from securefabric_domain.sync.scheduler import Scheduler

        self.p = platform
        self.scheduler = Scheduler(platform)
        self.scheduler.maintenance_enabled = False
        self.executed: list[dict[str, Any]] = []

    async def claim(
        self, queue: str, n: int = 50, *, absurd_now: Any = None
    ) -> list[dict[str, Any]]:
        from securefabric_db import fetch_all

        async with self.p.sys_pool.connection() as conn:
            if absurd_now is not None:
                await conn.execute(
                    "select set_config('absurd.fake_now', %s, false)", (absurd_now.isoformat(),)
                )
            try:
                return await fetch_all(
                    conn, "select * from absurd.claim_task(%s, 'test-worker', 300, %s)", (queue, n)
                )
            finally:
                if absurd_now is not None:
                    await conn.execute("select set_config('absurd.fake_now', '', false)")

    async def complete(self, queue: str, run_id: Any, result: dict[str, Any]) -> None:
        async with self.p.sys_pool.connection() as conn:
            await conn.execute(
                "select absurd.complete_run(%s, %s, %s)", (queue, run_id, json.dumps(result))
            )

    async def step(
        self, *, queues: tuple[str, ...] = ("sync_interactive", "sync_bulk"), die_on: Any = None
    ) -> int:
        """One tick plus every task it admitted. Returns tasks executed."""
        from securefabric_domain.sync.handler import handle_slice

        await self.scheduler.tick()
        n = 0
        for queue in queues:
            for task in await self.claim(queue):
                params = task["params"]
                if die_on is not None and die_on(params):
                    continue  # the worker "died": the claim lapses and Absurd retries it
                result = await handle_slice(
                    self.p, UUID(params["run_id"]), UUID(params["environment_id"])
                )
                self.executed.append(result)
                await self.complete(queue, task["run_id"], result)
                n += 1
        await self.scheduler.tick()
        return n

    async def drain(self, *, max_steps: int = 50, advance: float = 0) -> None:
        """Step until nothing is admissible now (advancing the clock between steps)."""
        for _ in range(max_steps):
            ran = await self.step()
            if not ran:
                if advance and isinstance(self.p.clock, FrozenClock):
                    self.p.clock.advance(advance)
                    if not await self.step():
                        return
                else:
                    return


async def run_control(
    platform: Platform, *, transport: Any = None, max_rounds: int = 5
) -> list[dict[str, Any]]:
    """Execute pending control-queue tasks as the control worker would."""
    from securefabric_db import fetch_all

    results: list[dict[str, Any]] = []
    for _ in range(max_rounds):
        async with platform.sys_pool.connection() as conn:
            tasks = await fetch_all(
                conn, "select * from absurd.claim_task('control', 'test-control', 300, 50)"
            )
        if not tasks:
            break
        for task in tasks:
            params = task["params"]
            name = task["task_name"]
            if name == "connection.verify":
                from securefabric_domain.connections import verify_connection

                res = await verify_connection(
                    platform,
                    UUID(params["environment_id"]),
                    UUID(params["connection_id"]),
                    reason=params.get("reason", "create"),
                    staged=params.get("staged", False),
                )
            elif name == "connect.complete":
                from securefabric_domain.connect import complete_redirect

                res = await complete_redirect(
                    platform, params["state"], UUID(params["environment_id"]), transport=transport
                )
            elif name == "ingress.process":
                from securefabric_domain.ingress import process_delivery

                res = await process_delivery(platform, UUID(params["delivery_row_id"]))
            elif name == "action.perform":
                from securefabric_domain.actions import perform_action

                res = await perform_action(
                    platform, UUID(params["environment_id"]), UUID(params["action_id"])
                )
            elif name == "passthrough.request":
                from securefabric_domain.passthrough import perform

                res = await perform(
                    platform,
                    UUID(params["environment_id"]),
                    UUID(params["connection_id"]),
                    params["method"],
                    params["path"],
                    params.get("query") or {},
                )
            elif name == "operator.repair":
                from securefabric_domain.operator import perform_repair

                res = await perform_repair(
                    platform,
                    UUID(params["environment_id"]),
                    UUID(params["connection_id"]),
                    params["action"],
                    params.get("params") or {},
                )
            elif name == "raw.read":
                from securefabric_domain.operator import read_raw

                res = await read_raw(
                    platform, UUID(params["environment_id"]), UUID(params["raw_page_id"])
                )
            else:
                res = {"skipped": name}
            results.append({"task": name, **res})
            async with platform.sys_pool.connection() as conn:
                await conn.execute(
                    "select absurd.complete_run('control', %s, %s)",
                    (task["run_id"], json.dumps(res, default=str)),
                )
    return results


async def reset_queues(platform: Platform) -> None:
    """Empty every Absurd queue and quiesce earlier tests' events (tests share one database)."""
    async with platform.sys_pool.connection() as conn:
        await conn.execute(
            "update events.outbox_event set dispatched_at = now() where dispatched_at is null"
        )
        await conn.execute("update events.webhook_endpoint set enabled = false where enabled")
        await conn.execute("delete from sync.dirty_record")
        await conn.execute("delete from sync.rate_bucket")
        await conn.execute("""update sync.stream_run set state = 'CANCELLED', finished_at = now()
                               where state in ('QUEUED', 'ADMITTED', 'RUNNING', 'PARKED', 'RETRY_WAIT')""")
        for q in ("sync_interactive", "sync_bulk", "control", "delivery", "maintenance"):
            for prefix in ("c", "r", "t"):
                await conn.execute(f"delete from absurd.{prefix}_{q}")  # noqa: S608


async def run_deliveries(platform: Platform) -> list[dict[str, Any]]:
    """Execute pending delivery tasks: one attempt each (durable sleeps are Absurd's job)."""
    from securefabric_db import fetch_all
    from securefabric_domain.events.delivery import deliver_with_retries

    out: list[dict[str, Any]] = []
    async with platform.sys_pool.connection() as conn:
        tasks = await fetch_all(
            conn, "select * from absurd.claim_task('delivery', 'test-delivery', 300, 100)"
        )
    for t in tasks:
        res = await deliver_with_retries(
            platform, UUID(t["params"]["environment_id"]), UUID(t["params"]["delivery_id"])
        )
        out.append(res)
        async with platform.sys_pool.connection() as conn:
            await conn.execute(
                "select absurd.complete_run('delivery', %s, %s)", (t["run_id"], json.dumps(res))
            )
    return out
