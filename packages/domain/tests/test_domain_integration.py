"""The control plane against a real Postgres: seed, read, and the sync lifecycle."""

from collections.abc import AsyncIterator
from typing import Any

import psycopg
import pytest

from securefabric_core import ConflictError, ValidationFailedError
from securefabric_domain import load_workspace, seed, service
from securefabric_domain.models import (
    ConnectionCreate,
    CustomerInput,
    EnvironmentCreate,
    IntegrationPatch,
    Workspace,
)
from securefabric_domain.status import collect

pytestmark = pytest.mark.integration


@pytest.fixture
async def conn(database_url: str) -> AsyncIterator[psycopg.AsyncConnection[Any]]:
    async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as c:
        await seed(c, reset=True)
        yield c


async def snapshot(conn: psycopg.AsyncConnection[Any]) -> Workspace:
    ws = await load_workspace(conn)
    assert ws is not None
    return ws


def _customer() -> CustomerInput:
    return CustomerInput(email="sec@contoso.com", end_user_id="org_contoso", org_name="Contoso")


async def test_seed_matches_what_the_dash_shows(conn: psycopg.AsyncConnection[Any]) -> None:
    ws = await snapshot(conn)
    assert [e.slug for e in ws.environments] == ["dev", "prod"]
    dev, prod = ws.environments
    assert {i.id for i in dev.integrations} == {
        "tenable",
        "qualys",
        "crowdstrike",
        "wiz",
        "okta",
        "snyk",
    }
    assert sum(c.sandbox for c in dev.connections) == 5
    assert len(prod.connections) == 14
    assert all(len(c.jobs) <= 40 for e in ws.environments for c in e.connections)
    assert len(prod.operations) <= 800
    starts = [o.started_at for o in prod.operations]
    assert starts == sorted(starts, reverse=True)
    assert len(ws.members) == 5
    assert await seed(conn) is False  # already seeded


async def test_connection_sync_lifecycle(conn: psycopg.AsyncConnection[Any]) -> None:
    connection_id, job_id = await service.create_connection(
        conn,
        "prod",
        ConnectionCreate(
            integration_id="tenable",
            customer=_customer(),
            credentials={"access_key": "AK1", "secret_key": "topsecret1234"},
        ),
    )
    created = next(
        c for c in (await snapshot(conn)).environments[1].connections if c.id == connection_id
    )
    assert created.health == "SYNCING"
    assert created.jobs[0].status == "RUNNING"
    assert created.credentials["secret_key"].endswith("1234")
    assert "topsecret" not in created.credentials["secret_key"]

    with pytest.raises(ConflictError):
        await service.trigger_sync(conn, "prod", connection_id)

    outcome = await service.finish_sync(conn, connection_id, job_id)
    assert outcome["status"] == "SUCCESS"
    assert outcome["added"] > 0
    # Replays (an Absurd retry after a crash) are no-ops.
    assert (await service.finish_sync(conn, connection_id, job_id))["status"] == "skipped"

    prod = (await snapshot(conn)).environments[1]
    synced = next(c for c in prod.connections if c.id == connection_id)
    assert synced.health == "HEALTHY"
    assert synced.counts["vulnerabilities"] > 0
    assert synced.last_sync_at is not None
    actions = [o.action for o in prod.operations if o.connection_id == connection_id]
    assert "sync.initial" in actions
    assert "connection.created" in actions
    assert "webhook.connection.sync.succeeded" in actions


async def test_unauthorized_connections_fail_fast(conn: psycopg.AsyncConnection[Any]) -> None:
    prod = (await snapshot(conn)).environments[1]
    hooli = next(c for c in prod.connections if c.health == "UNAUTHORIZED")
    job_id, outcome = await service.trigger_sync(conn, "prod", hooli.id)
    assert outcome == "failed"
    job = next(
        j
        for c in (await snapshot(conn)).environments[1].connections
        if c.id == hooli.id
        for j in c.jobs
        if j.id == job_id
    )
    assert job.status == "FAILED"
    assert job.failure_reason is not None


async def test_integration_rename_carries_connections(
    conn: psycopg.AsyncConnection[Any],
) -> None:
    new_id = await service.update_integration(
        conn, "prod", "wiz", IntegrationPatch(id="wiz-cloud", display_name="Wiz (cloud)")
    )
    assert new_id == "wiz-cloud"
    prod = (await snapshot(conn)).environments[1]
    assert {c.integration_id for c in prod.connections if c.provider == "wiz"} == {"wiz-cloud"}

    with pytest.raises(ConflictError):
        await service.update_integration(conn, "prod", "okta", IntegrationPatch(id="wiz-cloud"))


async def test_sandbox_is_off_in_production(conn: psycopg.AsyncConnection[Any]) -> None:
    with pytest.raises(ValidationFailedError):
        await service.create_connection(
            conn,
            "prod",
            ConnectionCreate(integration_id="okta", customer=_customer(), sandbox=True),
        )


async def test_environment_copy_and_keys(conn: psycopg.AsyncConnection[Any]) -> None:
    slug = await service.create_environment(
        conn, EnvironmentCreate(name="Staging", copy_from="dev")
    )
    assert slug == "staging"
    staging = next(e for e in (await snapshot(conn)).environments if e.slug == "staging")
    assert len(staging.integrations) == 6
    assert staging.connections == []
    default = next(k for k in staging.api_keys if k.is_default)
    assert default.preview.startswith("sk_test")

    rolled = await service.roll_api_key(conn, "staging", default.id)
    after = next(e for e in (await snapshot(conn)).environments if e.slug == "staging")
    assert after.keys.secret == rolled.secret
    assert rolled.key.preview != default.preview
    with pytest.raises(ConflictError):
        await service.revoke_api_key(conn, "staging", default.id)


async def test_status_reports_the_workspace(conn: psycopg.AsyncConnection[Any]) -> None:
    status = await collect(conn, version="test", environment="test")
    names = {c.name: c for c in status.components}
    assert names["database"].status == "ok"
    assert names["migrations"].status == "ok"
    assert status.workspace is not None
    assert status.workspace.seeded
    assert sum(e.connections for e in status.workspace.environments) == 20
