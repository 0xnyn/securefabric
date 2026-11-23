"""M4: connection lifecycle through the API, verification in the control worker,
initial job, data, pause/resume, delete, rotation, test endpoint."""

from typing import Any
from uuid import UUID

import pytest

from securefabric_db import fetch_one, fetch_required, tenant_tx
from securefabric_domain.testing import EngineDriver, run_control

pytestmark = pytest.mark.integration


async def org(api, ident="acme"):
    return (
        await api.post("/v1/organizations", {"identifier": ident, "name": ident.title()})
    ).json()["id"]


async def test_sandbox_connection_lifecycle(api) -> None:
    org_id = await org(api)
    r = await api.post(
        f"/v1/organizations/{org_id}/connections",
        {
            "vendor": "SANDBOX",
            "credentials": {"api_key": "sbx_lifecycle_1"},
            "identifier": "main",
            "options": {"finding_count": 25, "host_count": 8, "image_count": 4},
            "tags": {"env": "prod"},
        },
    )
    assert r.status_code == 201, r.text
    c = r.json()
    assert (
        c["state"] == "PENDING" and "credentials" not in c and c["health"]["name"] == "INITIALIZING"
    )
    results = await run_control(api.worker)
    assert results and results[0]["is_valid"] is True, results
    c = (await api.get(f"/v1/connections/{c['id']}")).json()
    assert c["state"] == "ACTIVE" and c["connection_config"]["tenant_id"].startswith("t_")
    assert {s["name"]: s["grant"] for s in c["streams"]}["findings"] == "GRANTED"
    assert c["authorization"]["fields_set"] == ["api_key"]
    await EngineDriver(api.worker).drain()
    c = (await api.get(f"/v1/connections/{c['id']}")).json()
    assert c["health"]["name"] == "HEALTHY" and c["health"]["status"] == "HEALTHY"
    counts = {s["name"]: s["record_count"] for s in c["streams"]}
    assert counts["findings"] == 25 and counts["hosts"] == 8
    jobs = (await api.get(f"/v1/connections/{c['id']}/jobs")).json()
    assert jobs[0]["type"] == "INITIAL" and jobs[0]["status"] == "SUCCESS"
    logs = (await api.get(f"/v1/jobs/{jobs[0]['id']}/logs")).json()
    assert any(line["kind"] == "http" for line in logs)
    # Filters: tags, vendor, health.
    assert (await api.get("/v1/connections", params={"tags[env]": "prod"})).json()["items"][0][
        "id"
    ] == c["id"]
    assert (await api.get("/v1/connections", params={"healthStatus": "UNHEALTHY"})).json()[
        "items"
    ] == []
    # Duplicate tenant in the same organization is refused at verification (AUTH-10).
    dup = (
        await api.post(
            f"/v1/organizations/{org_id}/connections",
            {
                "vendor": "SANDBOX",
                "credentials": {"api_key": "sbx_lifecycle_1"},
                "options": {"finding_count": 25, "host_count": 8, "image_count": 4},
            },
        )
    ).json()
    [res] = await run_control(api.worker)
    assert res["is_valid"] is False and "already connected" in res["message"]
    assert (await api.get(f"/v1/connections/{dup['id']}")).json()["state"] == "PENDING"
    # Pause / resume / illegal transition.
    assert (await api.patch(f"/v1/connections/{c['id']}", {"state": "PAUSED"})).json()[
        "state"
    ] == "PAUSED"
    assert (await api.patch(f"/v1/connections/{c['id']}", {"state": "ACTIVE"})).json()[
        "state"
    ] == "ACTIVE"
    bad = await api.patch(f"/v1/connections/{dup['id']}", {"state": "PAUSED"})
    assert bad.status_code == 409 and bad.json()["code"] == "invalid_state_transition"
    # Metadata cap (CON-10).
    big = await api.client.put(
        f"/v1/connections/{c['id']}/metadata", json={"x": "y" * 17000}, headers=api.h()
    )
    assert big.status_code == 422
    assert (await api.patch(f"/v1/connections/{c['id']}/metadata", {"team": "red"})).json() == {
        "team": "red"
    }
    # Delete (CON-04): credential row gone, 404 afterwards, event in the outbox.
    assert (await api.delete(f"/v1/connections/{c['id']}")).status_code == 204
    assert (await api.get(f"/v1/connections/{c['id']}")).status_code == 404
    async with tenant_tx(api.worker.pool, api.tenant.environment_id) as conn:
        assert (
            await fetch_one(
                conn, "select 1 from control.credential where connection_id = %s", (c["id"],)
            )
            is None
        )
        ev = await fetch_required(
            conn,
            "select type from events.outbox_event where connection_id = %s and type = 'connection.deleted'",
            (c["id"],),
        )
    assert ev is not None


async def test_bad_credentials_stay_pending_and_emit_create_failed(api) -> None:
    org_id = await org(api, "bad")
    c = (
        await api.post(
            f"/v1/organizations/{org_id}/connections",
            {"vendor": "SANDBOX", "credentials": {"api_key": "sbx_revoked_key"}},
        )
    ).json()
    [res] = await run_control(api.worker)
    assert res["is_valid"] is False
    got = (await api.get(f"/v1/connections/{c['id']}")).json()
    assert got["state"] == "PENDING" and got["pending_detail"]
    async with tenant_tx(api.worker.pool, api.tenant.environment_id) as conn:
        ev = await fetch_required(
            conn,
            "select payload from events.outbox_event where connection_id = %s and type = 'connection.create.failed'",
            (c["id"],),
        )
    assert ev["payload"]["data"]["error"] == "UNAUTHORIZED"


async def test_invalid_credentials_never_echo_the_value(api) -> None:
    org_id = await org(api, "echo")
    r = await api.post(
        f"/v1/organizations/{org_id}/connections",
        {"vendor": "SANDBOX", "credentials": {"api_key": "not-a-sandbox-key-secret-xyz"}},
    )
    assert r.status_code == 422 and "not-a-sandbox-key-secret-xyz" not in r.text


async def test_credential_rotation_verifies_before_swapping(api) -> None:
    org_id = await org(api, "rot")
    c = (
        await api.post(
            f"/v1/organizations/{org_id}/connections",
            {"vendor": "SANDBOX", "credentials": {"api_key": "sbx_rotate_old"}},
        )
    ).json()
    await run_control(api.worker)
    # A failing rotation leaves the old credential syncing.
    await api.patch(f"/v1/connections/{c['id']}", {"credentials": {"api_key": "sbx_revoked_new"}})
    [res] = await run_control(api.worker)
    assert res["is_valid"] is False
    test = (await api.get(f"/v1/connections/{c['id']}/test", params={"wait": 0.5})).json()
    # The test endpoint waits for a worker; nothing runs it here, so it reports pending...
    assert test["is_valid"] is False
    from securefabric_domain.sync.credentials import open_credentials

    assert (await open_credentials(api.worker, api.tenant.environment_id, c["id"]))[
        "api_key"
    ] == "sbx_rotate_old"
    await api.patch(f"/v1/connections/{c['id']}", {"credentials": {"api_key": "sbx_rotate_new"}})
    results = await run_control(api.worker)
    assert any(r.get("is_valid") for r in results)
    assert (await open_credentials(api.worker, api.tenant.environment_id, c["id"]))[
        "api_key"
    ] == "sbx_rotate_new"


async def test_operations_log_and_usage(api) -> None:
    org_id = await org(api, "ops")
    c = (
        await api.post(
            f"/v1/organizations/{org_id}/connections",
            {
                "vendor": "SANDBOX",
                "credentials": {"api_key": "sbx_ops_key"},
                "options": {"finding_count": 5},
            },
        )
    ).json()
    await run_control(api.worker)
    await EngineDriver(api.worker).drain()
    ops = (await api.get("/v1/operations", params={"connectionId": c["id"]})).json()["items"]
    kinds = {o["kind"] for o in ops}
    assert {"auth", "sync"} <= kinds and all(o["status"] in ("success", "warning") for o in ops)
    sync_op = next(o for o in ops if o["kind"] == "sync" and o["line_count"])
    detail = (await api.get(f"/v1/operations/{sync_op['id']}")).json()
    assert detail["lines"] and any(line["kind"] == "http" for line in detail["lines"])
    assert all("sbx_ops_key" not in line["message"] for line in detail["lines"])
    page = (await api.get("/v1/operations", params={"kind": "sync", "limit": 1})).json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    usage = (await api.get("/v1/usage")).json()
    assert usage["live"]["active_connections"] >= 1 and usage["live"]["records_stored"] >= 5


async def test_a_crashed_verification_is_visible_and_a_retest_recovers(api) -> None:
    from securefabric_domain.connections import VERIFY_CRASH_DETAIL, record_verify_crash

    org_id = await org(api, "crash")
    c = (
        await api.post(
            f"/v1/organizations/{org_id}/connections",
            {"vendor": "SANDBOX", "credentials": {"api_key": "sbx_crash_1"}},
        )
    ).json()
    env, cid = api.tenant.environment_id, UUID(c["id"])
    boom = RuntimeError("cannot import name 'x' (token sbx_crash_1)")

    # Not the last attempt: Absurd retries, nothing customer-visible changes.
    await record_verify_crash(api.worker, env, cid, reason="create", error=boom, final=False)
    assert (await api.get(f"/v1/connections/{cid}")).json()["health"]["name"] == "INITIALIZING"

    # The last attempt: no more silent PENDING.
    await record_verify_crash(api.worker, env, cid, reason="create", error=boom, final=True)
    got = (await api.get(f"/v1/connections/{cid}")).json()
    assert got["state"] == "PENDING" and got["health"]["name"] == "INTERNAL_ERROR"
    assert got["health"]["resolution_owner"] == "PLATFORM"
    async with tenant_tx(api.worker.pool, env) as conn:
        ev = await fetch_required(
            conn,
            "select payload from events.outbox_event where connection_id = %s "
            "and type = 'connection.create.failed'",
            (cid,),
        )
    assert ev["payload"]["data"]["error"] == "INTERNAL_ERROR"
    assert ev["payload"]["data"]["description"] == VERIFY_CRASH_DETAIL
    async with api.worker.sys_pool.connection() as conn:
        alert = await fetch_required(
            conn,
            "select detail from obs.alert where name = 'internal_error' and subject = %s "
            "and resolved_at is null",
            (f"verify:{cid}",),
        )
    # Exception text is never copied (it can carry anything); only the type is kept.
    assert alert["detail"]["error_type"] == "RuntimeError"
    assert "sbx_crash_1" not in str(alert["detail"]) and "sbx_crash_1" not in str(got)

    # Testing a never-activated connection retries its creation and activates it.
    await api.get(f"/v1/connections/{cid}/test", params={"wait": 0.5})
    # (The simulated crash left the original create task queued too; both now succeed.)
    results = await run_control(api.worker)
    assert results and all(r["is_valid"] for r in results), results
    got = (await api.get(f"/v1/connections/{cid}")).json()
    assert got["state"] == "ACTIVE" and got["health"]["name"] == "INITIALIZING"
    async with tenant_tx(api.worker.pool, env) as conn:
        row = await fetch_required(
            conn, "select pending_detail from control.connection where id = %s", (cid,)
        )
    assert row["pending_detail"] is None


async def test_connect_status_reports_the_last_verification(api) -> None:
    org_id = await org(api, "lastver")
    c = (
        await api.post(
            f"/v1/organizations/{org_id}/connections",
            {"vendor": "SANDBOX", "credentials": {"api_key": "sbx_lastver_old"}},
        )
    ).json()
    await run_control(api.worker)
    session = await api.post(
        "/v1/connect_sessions", {"organization_id": org_id, "connection_id": c["id"]}
    )
    assert session.status_code == 201, session.text
    token = session.json()["token"]

    async def status() -> dict[str, Any]:
        r = await api.get(f"/v1/connect/connections/{c['id']}", key=token)
        assert r.status_code == 200, r.text
        body: dict[str, Any] = r.json()
        return body

    first = (await status())["last_verification"]
    assert first["reason"] == "create" and first["status"] == "success"
    assert first["message"] and first["at"].endswith("Z")

    # A rejected rotation is discarded; the connect UI can now tell it apart from success.
    await api.patch(f"/v1/connections/{c['id']}", {"credentials": {"api_key": "sbx_revoked_rot"}})
    await run_control(api.worker)
    body = await status()
    assert body["state"] == "ACTIVE"
    last = body["last_verification"]
    assert last["reason"] == "rotate" and last["status"] == "failed" and last["message"]
    assert "sbx_revoked_rot" not in str(body)


async def test_github_sandbox_connection_replays_recorded_fixtures(api) -> None:
    """TEN-13: a sandbox connection of a real connector needs no credentials, never calls
    the vendor, and returns that connector's recorded data through the same pipeline."""
    import json
    from pathlib import Path

    from securefabric_connectors.github.connector import GitHubConnector

    def no_network():
        raise AssertionError("a sandbox connection must not reach the vendor")

    api.worker.vendor_transport = no_network
    org_id = await org(api, "gh-sandbox")
    r = await api.post(
        f"/v1/organizations/{org_id}/connections", {"vendor": "GITHUB", "is_sandbox": True}
    )
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["is_sandbox"] is True and c["state"] == "PENDING"
    [res] = await run_control(api.worker)
    assert res["is_valid"] is True, res
    await EngineDriver(api.worker).drain()
    got = (await api.get(f"/v1/connections/{c['id']}")).json()
    assert got["state"] == "ACTIVE" and got["health"]["name"] == "HEALTHY", got["health"]
    counts = {s["name"]: s["record_count"] for s in got["streams"]}
    fixtures = GitHubConnector().package_dir() / "fixtures"
    recorded_repos: set[int] = set()
    for i in json.loads(Path(fixtures / "repositories.json").read_text())["interactions"]:
        body = i["response"]["body"]
        rows = body.get("repositories", []) if isinstance(body, dict) else body
        recorded_repos |= {r["id"] for r in rows if isinstance(r, dict) and "full_name" in r}
    assert counts["repositories"] == len(recorded_repos) > 0
    assert counts["code_scanning_alerts"] > 0 and counts["dependabot_alerts"] > 0
    findings = (
        await api.get(
            "/v1/vulnerability_findings", headers={"X-CONNECTION-ID": c["id"]}, params={"limit": 5}
        )
    ).json()
    assert (
        findings["items"]
        and findings["items"][0]["vendor_attributes"]["data"]["vendor"] == "GITHUB"
    )
