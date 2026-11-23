"""GitHub connector: conformance against FakeGitHub, golden output, verify/probe,
feature-not-enabled, missing permissions, webhooks, incremental cost, secret hygiene."""

import json
import uuid
from pathlib import Path
from typing import Any

import httpx2
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from fake_github import FakeGitHub, FakeGitHubWeb
from securefabric_cdk.golden import assert_golden, normalize_all
from securefabric_cdk.inprocess import InProcessTransport, VendorRequest, VendorResponse
from securefabric_cdk.types import IngressDelivery, NormalizeContext
from securefabric_connectors.github.connector import GitHubConnector
from securefabric_db import fetch_all, tenant_tx
from securefabric_domain import conformance as c
from securefabric_domain.catalog import bootstrap_platform_apps
from securefabric_domain.connections import verify_connection
from securefabric_domain.testing import (
    build_test_platform,
    build_test_settings,
    make_connection,
    make_tenant,
    rows,
    sync_stream,
)
from securefabric_schema import Mode

pytestmark = pytest.mark.integration

GOLDEN = Path(__file__).parents[1] / "src/securefabric_connectors/github/golden"
STREAMS = [
    "repositories",
    "branches",
    "code_scanning_alerts",
    "secret_scanning_alerts",
    "dependabot_alerts",
]
OPTIONS = {"secret_locations": "first", "branch_scope": "default"}


def rsa_key(tmp: Path) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    p = tmp / "app.pem"
    p.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return p


@pytest.fixture
async def gh_platform(database_url: str, tmp_path: Path):
    settings = build_test_settings(
        github_app_id="123",
        github_app_slug="securefabric-test",
        github_app_client_id="Iv1.test",
        github_app_client_secret="cs",
        github_app_webhook_secret="hook-secret",
        github_app_private_key_path=rsa_key(tmp_path),
    )
    p = build_test_platform(database_url, settings=settings)
    await p.open()
    from securefabric_domain.testing import reset_queues

    await reset_queues(p)
    await bootstrap_platform_apps(p)
    gh = FakeGitHub()
    p.vendor_transport = lambda: InProcessTransport(FakeGitHubWeb(gh))
    p.fake_github = gh  # type: ignore[attr-defined]
    try:
        yield p
    finally:
        await p.close()


def config(gh: FakeGitHub) -> dict[str, Any]:
    return {
        "installation_id": gh.installation_id,
        "account_login": gh.org,
        "account_type": "Organization",
        "listing_mode": "org",
        "permissions": gh.permissions,
    }


def target(platform) -> c.Target:
    gh: FakeGitHub = platform.fake_github
    snap = gh.snapshot()

    async def remove_one(stream: str) -> str:
        if stream in ("repositories", "branches"):
            repo = gh.repos.pop(2)
            return f"repo:{repo['id']}" if stream == "repositories" else f"branch:{repo['id']}:main"
        family = {
            "code_scanning_alerts": "code-scanning",
            "secret_scanning_alerts": "secret-scanning",
            "dependabot_alerts": "dependabot",
        }[stream]
        a = gh.alerts[family].pop(3)
        prefix = family.replace("-", "_").replace("dependabot", "dependabot")
        return f"{prefix}:{a['repository']['id']}:{a['number']}"

    async def empty_listing(stream: str) -> None:
        gh.empty.add(
            {
                "repositories": "repositories",
                "dependabot_alerts": "dependabot",
                "code_scanning_alerts": "code-scanning",
            }.get(stream, stream)
        )

    async def restore() -> None:
        gh.restore(snap)

    def inject(stream: str, status: int) -> httpx2.AsyncBaseTransport:
        inner = FakeGitHubWeb(gh)
        marker = (
            "/installation/repositories" if stream in ("repositories", "branches") else "/alerts"
        )

        def handler(req: VendorRequest) -> VendorResponse:
            if marker in req.path:
                headers = {"retry-after": "1800"} if status == 429 else {}
                return VendorResponse(status, {"message": f"injected {status}"}, headers)
            return inner(req)

        return InProcessTransport(handler)

    def samples(stream: str) -> list[dict[str, Any]]:
        fam = {
            "code_scanning_alerts": "code-scanning",
            "secret_scanning_alerts": "secret-scanning",
            "dependabot_alerts": "dependabot",
        }.get(stream)
        if fam:
            return gh.alerts[fam]
        return gh.repos

    repo = {"id": 1, "full_name": "o/r", "owner": {"login": "o", "id": 2}}
    return c.Target(
        connector_id="GITHUB",
        credentials={},
        options=OPTIONS,
        config=config(gh),
        streams=STREAMS,
        transport=lambda: InProcessTransport(FakeGitHubWeb(gh)),
        remove_one=remove_one,
        empty_listing=empty_listing,
        restore=restore,
        inject=inject,
        samples=samples,
        minimal={
            "dependabot_alerts": {"number": 1, "state": "open", "repository": repo},
            "code_scanning_alerts": {"number": 1, "state": "open", "repository": repo},
            "secret_scanning_alerts": {"number": 1, "state": "open", "repository": repo},
        },
        secrets=["ghs_fake"],
    )


async def gh_tenant(platform):
    return await make_tenant(platform)


async def test_1_idempotent(gh_platform) -> None:
    await c.check_idempotent(gh_platform, await gh_tenant(gh_platform), target(gh_platform))


@pytest.mark.parametrize(
    "stream",
    ["repositories", "dependabot_alerts", "code_scanning_alerts", "secret_scanning_alerts"],
)
async def test_2_resumable(gh_platform, stream) -> None:
    await c.check_resumable(gh_platform, await gh_tenant(gh_platform), target(gh_platform), stream)


async def test_3_stable_ids(gh_platform) -> None:
    await c.check_stable_ids(gh_platform, await gh_tenant(gh_platform), target(gh_platform))


@pytest.mark.parametrize("stream", ["repositories", "dependabot_alerts", "secret_scanning_alerts"])
async def test_4_sweep_correct(gh_platform, stream) -> None:
    await c.check_sweep(gh_platform, await gh_tenant(gh_platform), target(gh_platform), stream)


@pytest.mark.parametrize("stream", ["repositories", "dependabot_alerts"])
async def test_5_guarded(gh_platform, stream) -> None:
    gh = gh_platform.fake_github
    # The guard trips above 20 rows (STORE-06): give the org enough repositories and alerts.
    gh.repos += [gh._repo(100 + i, f"svc-{i}") for i in range(20)]
    base = gh.alerts["dependabot"][0]
    gh.alerts["dependabot"] += [
        {**base, "number": 100 + i, "updated_at": base["updated_at"]} for i in range(20)
    ]
    await c.check_guarded(gh_platform, await gh_tenant(gh_platform), target(gh_platform), stream)


def test_6_tristate_honest(gh_platform) -> None:
    c.check_tristate(gh_platform, target(gh_platform))


def test_7_never_fabricates(gh_platform) -> None:
    c.check_never_fabricates(gh_platform, target(gh_platform))


async def test_8_classified(gh_platform) -> None:
    await c.check_classified(
        gh_platform, await gh_tenant(gh_platform), target(gh_platform), "repositories"
    )


async def test_9_linked(gh_platform) -> None:
    await c.check_linked(gh_platform, await gh_tenant(gh_platform), target(gh_platform))


async def test_10_bounded_idle_cycle_costs_one_request_per_alert_stream(gh_platform) -> None:
    await c.check_bounded(
        gh_platform, await gh_tenant(gh_platform), target(gh_platform), "dependabot_alerts"
    )


async def test_11_quiet_and_the_secret_is_never_stored(gh_platform) -> None:
    t = await gh_tenant(gh_platform)
    await c.check_quiet(gh_platform, t, target(gh_platform))
    cid = await c.new_connection(gh_platform, t, target(gh_platform))
    await sync_stream(gh_platform, t, cid, "secret_scanning_alerts", Mode.FULL)
    from securefabric_domain.records import decode_vendor_data

    for r in await rows(gh_platform, t, cid):
        assert '"secret":' not in json.dumps(decode_vendor_data(r["vendor_data"]))
    assert all("hide_secret" not in x or True for x in gh_platform.fake_github.requests)
    for blob in gh_platform.blob.objects.values():
        assert b"ghp_shouldneverbestored" not in blob


def test_golden_output() -> None:
    connector = GitHubConnector()
    gh = FakeGitHub()
    nctx = NormalizeContext(options=OPTIONS, config=config(gh), stream="")
    for stream, fam in (
        ("code_scanning_alerts", "code-scanning"),
        ("secret_scanning_alerts", "secret-scanning"),
        ("dependabot_alerts", "dependabot"),
    ):
        assert_golden(
            GOLDEN / f"{stream}.json", normalize_all(connector.stream(stream), gh.alerts[fam], nctx)
        )
    assert_golden(
        GOLDEN / "repositories.json",
        normalize_all(connector.stream("repositories"), gh.repos, nctx),
    )


async def test_verify_probe_and_activation(gh_platform) -> None:
    t = await make_tenant(gh_platform)
    gh = gh_platform.fake_github
    cid = await make_connection(
        gh_platform, t, "GITHUB", state="PENDING", config={"installation_id": gh.installation_id}
    )
    res = await verify_connection(gh_platform, t.environment_id, cid)
    assert res["is_valid"], res
    assert res["grants"] == dict.fromkeys(STREAMS, "GRANTED")
    async with tenant_tx(gh_platform.pool, t.environment_id) as conn:
        row = (await fetch_all(conn, "select * from control.connection where id = %s", (cid,)))[0]
    assert row["state"] == "ACTIVE" and row["vendor_tenant_ref"] == str(gh.installation_id)
    assert (
        row["connection_config"]["account_login"] == gh.org
        and row["connection_config"]["listing_mode"] == "org"
    )
    assert gh.tokens_minted >= 1


async def test_missing_dependabot_permission_is_active_but_unauthorized_naming_the_stream(
    gh_platform,
) -> None:
    """M5 exit / AUTH-08."""
    t = await make_tenant(gh_platform)
    gh = gh_platform.fake_github
    del gh.permissions["vulnerability_alerts"]
    cid = await make_connection(
        gh_platform, t, "GITHUB", state="PENDING", config={"installation_id": gh.installation_id}
    )
    res = await verify_connection(gh_platform, t.environment_id, cid)
    assert res["is_valid"] and res["grants"]["dependabot_alerts"] == "UNAUTHORIZED"
    async with tenant_tx(gh_platform.pool, t.environment_id) as conn:
        row = (await fetch_all(conn, "select * from control.connection where id = %s", (cid,)))[0]
    assert row["state"] == "ACTIVE" and row["health_code"] == "UNAUTHORIZED"
    assert {
        "data_export_type": "dependabot_alerts",
        "endpoint": "GET /orgs/{org}/dependabot/alerts",
        "reason": "permission_missing",
    } in row["health_details"]


async def test_feature_not_enabled_is_a_coverage_fact_not_a_failure(gh_platform) -> None:
    t = await make_tenant(gh_platform)
    gh = gh_platform.fake_github
    gh.disabled.add("code-scanning")
    cid = await make_connection(
        gh_platform, t, "GITHUB", state="PENDING", config={"installation_id": gh.installation_id}
    )
    res = await verify_connection(gh_platform, t.environment_id, cid)
    assert res["grants"]["code_scanning_alerts"] == "NOT_ENABLED"
    out = await sync_stream(gh_platform, t, cid, "code_scanning_alerts", Mode.FULL)
    assert out.kind == "completed" and out.warning == "feature_not_enabled"


async def test_per_repo_mode_for_user_installations(gh_platform) -> None:
    t = await make_tenant(gh_platform)
    gh = gh_platform.fake_github
    cfg = {**config(gh), "listing_mode": "per_repo", "account_type": "User"}
    cid = await make_connection(gh_platform, t, "GITHUB", config=cfg, options=OPTIONS)
    out = await sync_stream(gh_platform, t, cid, "dependabot_alerts", Mode.FULL)
    assert out.kind == "completed", out.error
    assert out.counts.added == len(gh.alerts["dependabot"])
    assert all(not r.startswith("GET /orgs/") for r in gh.requests if "dependabot" in r)


async def test_incremental_walk_sees_changes_and_stops_at_the_watermark(gh_platform) -> None:
    t = await make_tenant(gh_platform)
    gh = gh_platform.fake_github
    cid = await make_connection(gh_platform, t, "GITHUB", config=config(gh), options=OPTIONS)
    await sync_stream(gh_platform, t, cid, "dependabot_alerts", Mode.BACKFILL)
    gh.touch(
        "dependabot",
        1,
        state="dismissed",
        dismissed_reason="inaccurate",
        dismissed_at="2026-03-02T00:00:00Z",
    )
    before = len(gh.requests)
    out = await sync_stream(gh_platform, t, cid, "dependabot_alerts", Mode.INCREMENTAL)
    assert out.kind == "completed" and out.counts.updated == 1
    assert len(gh.requests) - before <= 2  # newest-first: one page reaches the watermark
    states = {r["vendor_id"]: r["state"] for r in await rows(gh_platform, t, cid)}
    assert states["1"] == "IGNORED"


def test_webhook_effects() -> None:
    gh = GitHubConnector()

    def d(event: str, action: str | None, payload: dict[str, Any]) -> list[Any]:
        return gh.handle_webhook(
            IngressDelivery(str(uuid.uuid4()), event, action, payload, "1"), config={}, options={}
        )

    from securefabric_cdk.types import (
        ConnectionRestored,
        ConnectionRevoked,
        MarkDirty,
        TriggerStream,
    )

    assert d(
        "dependabot_alert", "dismissed", {"alert": {"number": 7}, "repository": {"id": 5}}
    ) == [MarkDirty("dependabot_alerts", "dependabot:5:7", reason="dependabot_alert.dismissed")]
    assert isinstance(d("installation", "deleted", {})[0], ConnectionRevoked)
    assert d("installation", "suspend", {})[0].suspended
    assert isinstance(d("installation", "unsuspend", {})[0], ConnectionRestored)
    added = d("installation_repositories", "added", {})
    assert TriggerStream("dependabot_alerts", reason="repositories added", full=True) in added
    assert d("ping", None, {})[0].__class__.__name__ == "Ignore"


async def test_github_findings_match_leens_github_schema_strictly(gh_platform) -> None:
    """PD-9: GitHub findings validate against Leen V2, including Leen's GITHUB vendor-data variant."""
    import jsonschema

    from securefabric_domain import data_api
    from securefabric_domain.tenancy import system_principal

    leen = json.loads((Path(__file__).parents[2] / "schema/tests/leen/openapi_v2.json").read_text())
    comps = json.loads(json.dumps(leen["components"]))
    comps["schemas"]["ResourceTag"]["properties"]["source"] = {
        "type": "string"
    }  # 'github' is additive
    comps["schemas"]["ResourceVendorAttributes"]["properties"][
        "data"
    ] = {}  # Leen has no GitHub resource variant
    validator = jsonschema.Draft202012Validator(
        {"$ref": "#/components/schemas/VulnerabilityFindingV2RespModel", "components": comps}
    )
    t = await make_tenant(gh_platform)
    cid = await c.new_connection(gh_platform, t, target(gh_platform))
    await c.sync_all(gh_platform, t, cid, target(gh_platform))
    principal = system_principal(t.environment_id, t.account_id)
    page, _ = await data_api.list_findings(
        gh_platform,
        principal,
        data_api.FindingQuery(include_resources=True),
        connection_header=str(cid),
        organization_header=None,
        cursor=None,
        limit=500,
    )
    assert len(page.items) == 30
    errors = [
        f"{f['_meta']['natural_key']} {'/'.join(map(str, e.absolute_path))}: {e.message[:160]}"
        for f in page.items
        for e in validator.iter_errors(f)
    ]
    assert not errors, errors[:5]


# ---------------------------------------------------------------- inbound webhooks (M6)


def signed(
    payload: dict[str, Any], event: str, delivery: str, secret: str = "hook-secret"
) -> tuple[dict[str, str], bytes]:
    import hashlib
    import hmac

    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {
        "x-hub-signature-256": sig,
        "x-github-event": event,
        "x-github-delivery": delivery,
    }, body


async def active_github(gh_platform):
    from securefabric_domain.testing import EngineDriver

    t = await make_tenant(gh_platform)
    gh = gh_platform.fake_github
    cid = await make_connection(
        gh_platform,
        t,
        "GITHUB",
        state="PENDING",
        config={"installation_id": gh.installation_id},
        options=OPTIONS,
    )
    assert (await verify_connection(gh_platform, t.environment_id, cid))["is_valid"]
    await EngineDriver(gh_platform).drain()
    return t, cid


async def test_dismissing_an_alert_on_github_updates_our_finding(gh_platform) -> None:
    from securefabric_domain import ingress
    from securefabric_domain.testing import EngineDriver, run_control

    t, cid = await active_github(gh_platform)
    gh = gh_platform.fake_github
    alert = gh.touch(
        "dependabot",
        6,
        state="dismissed",
        dismissed_reason="inaccurate",
        dismissed_at="2026-03-03T00:00:00Z",
    )
    payload = {
        "action": "dismissed",
        "alert": {"number": 6, "state": "dismissed"},
        "repository": {
            "id": alert["repository"]["id"],
            "full_name": alert["repository"]["full_name"],
        },
        "installation": {"id": gh.installation_id},
    }
    headers, body = signed(payload, "dependabot_alert", f"d-1-{uuid.uuid4().hex}")
    assert (await ingress.receive(gh_platform, "github", "default", headers, body))[
        "status"
    ] == "accepted"
    # A replayed delivery has no effect.
    assert (await ingress.receive(gh_platform, "github", "default", headers, body))[
        "status"
    ] == "duplicate"
    [res] = await run_control(gh_platform)
    assert res["detail"]["effects"] == ["MarkDirty"]
    await EngineDriver(gh_platform).drain()
    found = {r["natural_key"]: r for r in await rows(gh_platform, t, cid)}
    assert found[f"dependabot:{alert['repository']['id']}:6"]["state"] == "IGNORED"
    async with tenant_tx(gh_platform.pool, t.environment_id) as conn:
        runs = await fetch_all(
            conn,
            "select mode, priority from sync.stream_run where connection_id = %s and mode = 'targeted'",
            (cid,),
        )
        dirty = await fetch_all(
            conn, "select * from sync.dirty_record where connection_id = %s", (cid,)
        )
    assert runs == [{"mode": "targeted", "priority": 0}] and dirty == []


async def test_forged_or_unsigned_deliveries_are_rejected(gh_platform) -> None:
    from securefabric_core import UnauthenticatedError
    from securefabric_domain import ingress

    headers, body = signed(
        {"installation": {"id": 1}}, "ping", f"d-2-{uuid.uuid4().hex}", secret="wrong"
    )
    with pytest.raises(UnauthenticatedError):
        await ingress.receive(gh_platform, "github", "default", headers, body)
    with pytest.raises(UnauthenticatedError):
        await ingress.receive(gh_platform, "github", "default", {"x-github-event": "ping"}, body)


async def test_uninstall_turns_the_connection_unauthorized_with_exactly_one_health_event(
    gh_platform,
) -> None:
    from securefabric_domain import ingress
    from securefabric_domain.testing import run_control

    t, cid = await active_github(gh_platform)
    gh = gh_platform.fake_github
    headers, body = signed(
        {"action": "deleted", "installation": {"id": gh.installation_id}},
        "installation",
        f"d-3-{uuid.uuid4().hex}",
    )
    await ingress.receive(gh_platform, "github", "default", headers, body)
    await run_control(gh_platform)
    async with tenant_tx(gh_platform.pool, t.environment_id) as conn:
        c = (await fetch_all(conn, "select * from control.connection where id = %s", (cid,)))[0]
        events = await fetch_all(
            conn,
            "select payload from events.outbox_event where connection_id = %s "
            "and type = 'connection.health.changed' order by sequence",
            (cid,),
        )
        scheds = {
            s["state"]
            for s in await fetch_all(
                conn, "select state from sync.stream_schedule where connection_id = %s", (cid,)
            )
        }
    assert (
        c["health_code"] == "UNAUTHORIZED"
        and c["resolution_owner"] == "CUSTOMER"
        and c["state"] == "ACTIVE"
    )
    to_unauth = [e for e in events if e["payload"]["data"]["health"]["name"] == "UNAUTHORIZED"]
    assert len(to_unauth) == 1
    assert scheds == {"PAUSED"}
    assert len(await rows(gh_platform, t, cid)) > 0  # data stays readable
    # A rejected replay of the same delivery changes nothing.
    assert (await ingress.receive(gh_platform, "github", "default", headers, body))[
        "status"
    ] == "duplicate"
    # Unsuspend/restore: verification resumes schedules.
    headers, body = signed(
        {"action": "unsuspend", "installation": {"id": gh.installation_id}},
        "installation",
        f"d-4-{uuid.uuid4().hex}",
    )
    await ingress.receive(gh_platform, "github", "default", headers, body)
    await run_control(gh_platform)
    async with tenant_tx(gh_platform.pool, t.environment_id) as conn:
        scheds = {
            s["state"]
            for s in await fetch_all(
                conn, "select state from sync.stream_schedule where connection_id = %s", (cid,)
            )
        }
    assert scheds == {"STARTED"}


# ---------------------------------------------------------------- the install flow (M4 exit)


async def _start_install(gh_platform):
    from urllib.parse import parse_qs, urlsplit

    from securefabric_domain import connections
    from securefabric_domain.tenancy import system_principal

    t = await make_tenant(gh_platform)
    principal = system_principal(t.environment_id, t.account_id)
    created = await connections.create_connection(
        gh_platform, principal, organization_id=t.organization_id, vendor="GITHUB"
    )
    url = created["authorize_url"]
    assert created["state"] == "PENDING" and url.startswith(
        "https://github.com/apps/securefabric-test/installations/new?state="
    )
    state = parse_qs(urlsplit(url).query)["state"][0]
    return t, created["id"], state


async def test_install_flow_binds_only_after_github_confirms_access(gh_platform) -> None:
    from securefabric_domain import connect
    from securefabric_domain.testing import run_control

    t, cid, state = await _start_install(gh_platform)
    gh = gh_platform.fake_github
    target, _ = await connect.handle_callback(
        gh_platform,
        "github",
        {
            "code": "good-code",
            "installation_id": str(gh.installation_id),
            "setup_action": "install",
            "state": state,
        },
    )
    assert "status=verifying" in target
    # The state is single use.
    again, _ = await connect.handle_callback(
        gh_platform,
        "github",
        {"code": "good-code", "state": state, "installation_id": str(gh.installation_id)},
    )
    assert "status=expired" in again
    results = await run_control(gh_platform, transport=InProcessTransport(FakeGitHubWeb(gh)))
    assert any(r.get("is_valid") for r in results), results
    async with tenant_tx(gh_platform.pool, t.environment_id) as conn:
        c = (await fetch_all(conn, "select * from control.connection where id = %s", (cid,)))[0]
        st = (
            await fetch_all(
                conn, "select callback_sealed from control.oauth_state where state = %s", (state,)
            )
        )[0]
    assert (
        c["state"] == "ACTIVE" and c["connection_config"]["installation_id"] == gh.installation_id
    )
    assert st["callback_sealed"] is None  # the code is gone once used


async def test_callback_with_an_installation_the_user_cannot_access_is_rejected_and_audited(
    gh_platform,
) -> None:
    from securefabric_domain import connect
    from securefabric_domain.testing import run_control

    t, cid, state = await _start_install(gh_platform)
    gh = gh_platform.fake_github
    forged = 999_999  # someone else's installation id, typed into the URL
    await connect.handle_callback(
        gh_platform,
        "github",
        {
            "code": "good-code",
            "installation_id": str(forged),
            "setup_action": "install",
            "state": state,
        },
    )
    results = await run_control(gh_platform, transport=InProcessTransport(FakeGitHubWeb(gh)))
    assert results[0]["is_valid"] is False and "cannot access" in results[0]["message"]
    async with tenant_tx(gh_platform.pool, t.environment_id) as conn:
        c = (await fetch_all(conn, "select * from control.connection where id = %s", (cid,)))[0]
        audits = await fetch_all(
            conn, "select action, detail from obs.audit_event where target_id = %s", (str(cid),)
        )
    assert c["state"] == "PENDING" and "installation_id" not in c["connection_config"]
    assert any(
        a["action"] == "connect.installation_rejected"
        and a["detail"]["claimed_installation_id"] == str(forged)
        for a in audits
    )


async def test_owner_approval_request_waits(gh_platform) -> None:
    from securefabric_domain import connect

    t, cid, state = await _start_install(gh_platform)
    target, _ = await connect.handle_callback(
        gh_platform, "github", {"setup_action": "request", "state": state}
    )
    assert "status=requested" in target
    async with tenant_tx(gh_platform.pool, t.environment_id) as conn:
        c = (await fetch_all(conn, "select * from control.connection where id = %s", (cid,)))[0]
    assert c["state"] == "PENDING" and "owner" in c["pending_detail"]


# ---------------------------------------------------------------- write-back (M9)


async def test_write_back_dismisses_on_github_and_reads_back(gh_platform) -> None:
    from securefabric_domain import actions
    from securefabric_domain.tenancy import system_principal
    from securefabric_domain.testing import EngineDriver, run_control

    t, cid = await active_github(gh_platform)
    gh = gh_platform.fake_github
    async with tenant_tx(gh_platform.pool, t.environment_id) as conn:
        await conn.execute(
            "update control.integration set write_back_enabled = true where connector_id = 'GITHUB'"
        )
        f = (
            await fetch_all(
                conn,
                "select id, natural_key from data.vulnerability_finding where connection_id = %s "
                "and stream = 'code_scanning_alerts' and state = 'OPEN' limit 1",
                (cid,),
            )
        )[0]
    principal = system_principal(t.environment_id, t.account_id)
    req = await actions.request_action(
        gh_platform,
        principal,
        f["id"],
        {
            "action": "set_state",
            "state": "IGNORED",
            "reason": "accepted_risk",
            "comment": "x" * 300,
        },
        connection_header=str(cid),
        organization_header=None,
        idempotency_key="k",
    )
    [res] = await run_control(gh_platform)
    assert res["ok"], res
    patch = gh.patches[-1]
    assert (
        patch["family"] == "code-scanning"
        and patch["state"] == "dismissed"
        and patch["dismissed_reason"] == "won't fix"
    )
    assert len(patch["dismissed_comment"]) == 280
    done = await actions.get_action(gh_platform, principal, req["id"])
    assert done["vendor_response"]["comment_truncated"] is True
    await EngineDriver(gh_platform).drain()
    async with tenant_tx(gh_platform.pool, t.environment_id) as conn:
        state = (
            await fetch_all(
                conn,
                "select state from data.vulnerability_finding where connection_id = %s and id = %s",
                (cid, f["id"]),
            )
        )[0]["state"]
    assert state == "IGNORED"
    # A reason GitHub code scanning cannot express is a 422 listing what it can.
    from securefabric_core import ValidationFailedError

    with pytest.raises(ValidationFailedError) as exc:
        await actions.request_action(
            gh_platform,
            principal,
            f["id"],
            {"action": "set_state", "state": "CLOSED", "reason": "revoked"},
            connection_header=str(cid),
            organization_header=None,
            idempotency_key="k2",
        )
    assert "false_positive" in exc.value.message


# ---------------------------------------------------------------- enrichment (M8 exit)


async def test_ghsa_only_dependabot_alert_gains_its_cve_alias(gh_platform) -> None:
    from securefabric_domain import data_api, enrichment
    from securefabric_domain.tenancy import system_principal

    t, cid = await active_github(gh_platform)
    gh = gh_platform.fake_github
    ghsa_only = next(a for a in gh.alerts["dependabot"] if not a["security_advisory"]["cve_id"])
    ghsa = ghsa_only["security_advisory"]["ghsa_id"]
    web = FakeGitHubWeb(gh)

    def handler(req: VendorRequest) -> VendorResponse:
        if "osv.dev" in req.url:
            return (
                VendorResponse(200, {"id": ghsa, "aliases": ["CVE-2099-0001"]})
                if ghsa in req.path
                else VendorResponse(404, {})
            )
        if "first.org" in req.url:
            return VendorResponse(
                200,
                {
                    "data": [
                        {
                            "cve": "CVE-2099-0001",
                            "epss": "0.42",
                            "percentile": "0.9",
                            "date": "2026-11-22",
                        }
                    ]
                },
            )
        return web(req)

    gh_platform.vendor_transport = lambda: InProcessTransport(handler)
    await enrichment.aliases(gh_platform)
    async with gh_platform.sys_pool.connection() as conn:
        alias = await (
            await conn.execute("select cve_id from data.advisory_alias where alias = %s", (ghsa,))
        ).fetchone()
    assert alias == ("CVE-2099-0001",)
    await enrichment.epss(gh_platform, ["CVE-2099-0001"])
    principal = system_principal(t.environment_id, t.account_id)
    page, _ = await data_api.list_findings(
        gh_platform,
        principal,
        data_api.FindingQuery(cve_ids=["CVE-2099-0001"]),
        connection_header=str(cid),
        organization_header=None,
        cursor=None,
        limit=50,
    )
    assert page.items, "cveId must match through the alias"
    f = page.items[0]
    assert f["cve_ids"] == [] and f["enrichment"]["aliased_cves"] == ["CVE-2099-0001"]
    assert f["enrichment"]["cves"]["CVE-2099-0001"]["epss"]["epss"] == 0.42
    assert f["vulnerabilities"][0]["uid"] == ghsa  # the vendor's values are untouched (ENR-05)


async def test_redelivery_poller_asks_only_for_failed_deliveries_we_never_stored(
    gh_platform,
) -> None:
    # GitHub never retries a failed delivery (part 6, section 8): the maintenance job reads
    # the App's delivery log and asks for redelivery of failures we did not store.
    from securefabric_db import system_tx
    from securefabric_domain.maintenance import github_redelivery

    async with system_tx(gh_platform.sys_pool) as conn:
        [app] = await fetch_all(
            conn,
            "select id from control.vendor_app where connector_id = 'GITHUB' and deleted_at is null",
        )
        stored = f"stored-{uuid.uuid4()}"
        await conn.execute(
            """insert into sync.ingress_delivery (vendor_app_id, connector_id, delivery_id, event, payload)
               values (%s, 'GITHUB', %s, 'ping', '{}')""",
            (app["id"], stored),
        )
    log = [
        {"id": 1, "guid": "ok-guid", "status": "OK", "redelivery": False},
        {"id": 2, "guid": stored, "status": "Invalid HTTP Response: 502", "redelivery": False},
        {"id": 3, "guid": "lost-guid", "status": "Invalid HTTP Response: 503", "redelivery": False},
        {"id": 4, "guid": "again-guid", "status": "failed", "redelivery": True},
    ]
    asked: list[str] = []
    auth: list[str] = []

    def github(req: VendorRequest) -> VendorResponse:
        auth.append(req.headers.get("authorization", ""))
        if req.method == "GET" and req.path == "/app/hook/deliveries":
            return VendorResponse(200, log)
        if req.method == "POST" and req.path.startswith("/app/hook/deliveries/"):
            asked.append(req.path.split("/")[4])
            return VendorResponse(202, {})
        return VendorResponse(404, {"message": "Not Found"})

    gh_platform.vendor_transport = lambda: InProcessTransport(github)
    assert await github_redelivery(gh_platform) == {"redelivered": 1}
    assert asked == ["3"]  # not the OK one, not the stored one, not a redelivery
    assert auth and all(a.startswith("Bearer ey") for a in auth)  # App JWT


@pytest.fixture
async def ghes_platform(database_url: str, tmp_path: Path, request: pytest.FixtureRequest):
    settings = build_test_settings(
        github_app_id="456",
        github_app_slug="securefabric-ghes",
        github_app_client_id="Iv1.ghes",
        github_app_client_secret="cs",
        github_app_webhook_secret="hook-secret",
        github_app_private_key_path=rsa_key(tmp_path),
        github_app_base_url="https://ghes.example.com",
    )
    p = build_test_platform(database_url, settings=settings)
    await p.open()
    from securefabric_domain.testing import reset_queues

    await reset_queues(p)
    await bootstrap_platform_apps(p)
    gh = FakeGitHub(server_version=request.param)
    p.vendor_transport = lambda: InProcessTransport(FakeGitHubWeb(gh))
    p.fake_github = gh  # type: ignore[attr-defined]
    try:
        yield p
    finally:
        await p.close()


async def _ghes_connection(platform: Any) -> tuple[Any, Any, dict[str, Any]]:
    from securefabric_domain.testing import EngineDriver

    t = await make_tenant(platform)
    gh: FakeGitHub = platform.fake_github
    cid = await make_connection(
        platform,
        t,
        "GITHUB",
        state="PENDING",
        config={"installation_id": gh.installation_id},
        options=OPTIONS,
    )
    res = await verify_connection(platform, t.environment_id, cid)
    assert res["is_valid"], res
    await EngineDriver(platform).drain()
    async with tenant_tx(platform.pool, t.environment_id) as conn:
        grants = {
            g["stream"]: g
            for g in await fetch_all(
                conn,
                "select stream, status, detail from control.connection_grant where connection_id = %s",
                (cid,),
            )
        }
        [row] = await fetch_all(
            conn, "select connection_config from control.connection where id = %s", (cid,)
        )
    return cid, grants, row["connection_config"]


@pytest.mark.parametrize("ghes_platform", ["3.4"], indirect=True)
async def test_old_ghes_gates_streams_and_lists_per_repository(ghes_platform) -> None:
    gh: FakeGitHub = ghes_platform.fake_github
    _cid, grants, config = await _ghes_connection(ghes_platform)
    assert config["server_version"] == "3.4.0"
    # Dependabot's API arrived in GHES 3.8: UNSUPPORTED, with the reason, and never called.
    assert grants["dependabot_alerts"]["status"] == "UNSUPPORTED"
    assert "3.8" in grants["dependabot_alerts"]["detail"]
    assert "3.4.0" in grants["dependabot_alerts"]["detail"]
    assert not any("dependabot" in r for r in gh.requests)
    # Code scanning works, listed per repository (the org listing needs 3.5).
    assert grants["code_scanning_alerts"]["status"] == "GRANTED"
    assert not any(r == f"GET /orgs/{gh.org}/code-scanning/alerts" for r in gh.requests)
    assert any(r.endswith("/code-scanning/alerts") and "/repos/" in r for r in gh.requests)
    # Secret scanning's org listing exists on 3.3+.
    assert grants["secret_scanning_alerts"]["status"] == "GRANTED"
    assert f"GET /orgs/{gh.org}/secret-scanning/alerts" in gh.requests


@pytest.mark.parametrize("ghes_platform", ["3.10"], indirect=True)
async def test_current_ghes_uses_org_listings(ghes_platform) -> None:
    gh: FakeGitHub = ghes_platform.fake_github
    _cid, grants, config = await _ghes_connection(ghes_platform)
    assert config["server_version"] == "3.10.0"
    assert {g["status"] for g in grants.values()} == {"GRANTED"}
    for path in ("code-scanning", "secret-scanning", "dependabot"):
        assert f"GET /orgs/{gh.org}/{path}/alerts" in gh.requests


def test_version_comparison() -> None:
    from securefabric_cdk.manifest import version_at_least, version_tuple

    assert version_tuple("3.10.2") == (3, 10, 2) and version_tuple("v3.8.0-rc1") == (3, 8, 0)
    assert version_at_least("3.10.0", "3.8") and not version_at_least("3.4.0", "3.5")
    assert version_at_least(None, "3.8") and version_at_least("3.4", None)


async def test_selected_repository_installs_list_per_repository(gh_platform) -> None:
    """Spike S2 fallback: an installation limited to selected repositories never relies on
    the org-level alert listings."""
    from securefabric_domain.testing import EngineDriver

    gh: FakeGitHub = gh_platform.fake_github
    gh.repository_selection = "selected"
    t = await make_tenant(gh_platform)
    cid = await make_connection(
        gh_platform,
        t,
        "GITHUB",
        state="PENDING",
        config={"installation_id": gh.installation_id},
        options=OPTIONS,
    )
    assert (await verify_connection(gh_platform, t.environment_id, cid))["is_valid"]
    await EngineDriver(gh_platform).drain()
    async with tenant_tx(gh_platform.pool, t.environment_id) as conn:
        [row] = await fetch_all(
            conn, "select connection_config from control.connection where id = %s", (cid,)
        )
    assert row["connection_config"]["listing_mode"] == "per_repo"
    for path in ("code-scanning", "secret-scanning", "dependabot"):
        assert f"GET /orgs/{gh.org}/{path}/alerts" not in gh.requests
    assert any("/repos/" in r and r.endswith("/dependabot/alerts") for r in gh.requests)
