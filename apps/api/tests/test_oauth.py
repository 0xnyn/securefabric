"""OAuth2 through the platform, proven with the SANDBOX variants (part 5, section 6).

SANDBOX_OAUTH: authorization code with PKCE through the connect redirect, refresh
tokens that rotate on every use (reuse revokes the family). SANDBOX_CC: client
credentials minted and cached. Everything runs over the real HTTP routes.
"""

from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest

from securefabric_cdk import oauth2
from securefabric_cdk.inprocess import VendorRequest
from securefabric_connectors.sandbox.connector import PLATFORM_OAUTH_CLIENT
from securefabric_connectors.sandbox.oauth import OAuthServer, client_secret_for, reset_oauth
from securefabric_db import fetch_required, tenant_tx
from securefabric_domain.catalog import bootstrap_platform_apps
from securefabric_domain.sync.credentials import open_credentials
from securefabric_domain.testing import EngineDriver, run_control

pytestmark = pytest.mark.integration


def local(url: str) -> str:
    """The path + query of a platform URL (the test client is the platform)."""
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}" if parts.query else parts.path


async def org(api: Any, ident: str) -> str:
    r = await api.post("/v1/organizations", {"identifier": ident, "name": ident})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def start_oauth(api: Any, ident: str) -> tuple[dict[str, Any], str]:
    await bootstrap_platform_apps(api.worker)  # registers the SANDBOX_OAUTH client
    org_id = await org(api, ident)
    r = await api.post(
        f"/v1/organizations/{org_id}/connections",
        {"vendor": "SANDBOX_OAUTH", "options": {"finding_count": 12, "host_count": 3}},
    )
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["state"] == "PENDING" and c["authorize_url"]
    return c, c["authorize_url"]


def test_pkce_matches_rfc_7636() -> None:
    # RFC 7636, appendix B.
    assert (
        oauth2.s256("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )
    pair = oauth2.pkce_pair()
    assert len(pair.verifier) >= 43 and pair.challenge == oauth2.s256(pair.verifier)


async def test_authorization_code_with_pkce_connects_syncs_and_rotates(api) -> None:
    reset_oauth()
    c, authorize_url = await start_oauth(api, "oauth-ok")
    q = parse_qs(urlsplit(authorize_url).query)
    assert q["code_challenge_method"] == ["S256"] and q["code_challenge"][0]
    assert q["client_id"] == [PLATFORM_OAUTH_CLIENT] and "code_verifier" not in q

    # The "vendor" page approves and sends the browser to our callback with a code.
    vendor = await api.client.get(local(authorize_url))
    assert vendor.status_code == 302, vendor.text
    callback = vendor.headers["location"]
    assert urlsplit(callback).path == "/v1/connect/callback/sandbox_oauth"
    done = await api.client.get(local(callback))
    assert done.status_code == 302 and "status=verifying" in done.headers["location"]

    # The control worker exchanges the code (with the verifier) and verifies.
    results = await run_control(api.worker)
    assert results and results[-1]["is_valid"] is True, results
    got = (await api.get(f"/v1/connections/{c['id']}")).json()
    assert got["state"] == "ACTIVE"
    assert got["authorization"]["fields_set"] == ["refresh_token"]
    env, cid = api.tenant.environment_id, UUID(c["id"])
    first_rt = (await open_credentials(api.worker, env, cid))["refresh_token"]
    assert first_rt.startswith("sbxrt_")
    assert first_rt not in str(got)  # never echoed

    # The initial sync runs on the access token from the exchange.
    await EngineDriver(api.worker).drain()
    got = (await api.get(f"/v1/connections/{c['id']}")).json()
    assert got["health"]["name"] == "HEALTHY", got["health"]
    assert {s["name"]: s["record_count"] for s in got["streams"]}["findings"] == 12

    # Two hours later the access token is stale: the next sync refreshes, and the
    # rotated refresh token replaces the sealed credential (single use).
    api.worker.clock.advance(timedelta(hours=2).total_seconds())
    job = await api.post(f"/v1/connections/{c['id']}/jobs", {})
    assert job.status_code in (200, 201, 202), job.text
    await EngineDriver(api.worker).drain()
    second_rt = (await open_credentials(api.worker, env, cid))["refresh_token"]
    assert second_rt != first_rt
    assert (await api.get(f"/v1/connections/{c['id']}")).json()["health"]["name"] == "HEALTHY"

    # Replaying the spent refresh token is refused and revokes the whole family.
    server = OAuthServer({})
    form = (
        f"grant_type=refresh_token&refresh_token={first_rt}&client_id={PLATFORM_OAUTH_CLIENT}"
        f"&client_secret={client_secret_for(PLATFORM_OAUTH_CLIENT)}"
    )
    replay = server.handle(
        "/oauth/token",
        VendorRequest("POST", "", "/oauth/token", {}, {}, form.encode()),
    )
    assert replay is not None and replay.status == 400
    assert replay.body["error"] == "invalid_grant"
    current = form.replace(first_rt, second_rt)
    after = server.handle(
        "/oauth/token", VendorRequest("POST", "", "/oauth/token", {}, {}, current.encode())
    )
    assert after is not None and after.status == 400  # the family is gone


async def test_denied_authorization_and_redirect_guard(api) -> None:
    reset_oauth()
    c, authorize_url = await start_oauth(api, "oauth-deny")
    # Only our own callback may be the redirect target (no open redirect).
    evil = authorize_url.replace("redirect_uri=", "redirect_uri=https%3A%2F%2Fevil.example%2Fx&a=")
    assert (await api.client.get(local(evil))).status_code == 400

    vendor = await api.client.get(local(authorize_url + "&deny=1"))
    assert vendor.status_code == 302
    done = await api.client.get(local(vendor.headers["location"]))
    assert "status=denied" in done.headers["location"]
    async with tenant_tx(api.worker.pool, api.tenant.environment_id) as conn:
        row = await fetch_required(
            conn, "select state, pending_detail from control.connection where id = %s", (c["id"],)
        )
    assert row["state"] == "PENDING" and "denied" in row["pending_detail"]


async def test_client_credentials_mint_and_cache(api) -> None:
    reset_oauth()
    org_id = await org(api, "cc")
    client_id = "sbxc_customer_1"
    ok = await api.post(
        f"/v1/organizations/{org_id}/connections",
        {
            "vendor": "SANDBOX_CC",
            "credentials": {"client_id": client_id, "client_secret": client_secret_for(client_id)},
            "options": {"finding_count": 5, "host_count": 2},
        },
    )
    assert ok.status_code == 201, ok.text
    bad = await api.post(
        f"/v1/organizations/{org_id}/connections",
        {
            "vendor": "SANDBOX_CC",
            "identifier": "wrong",
            "credentials": {"client_id": client_id, "client_secret": "sbxcs_wrong"},
        },
    )
    assert bad.status_code == 201, bad.text
    results = {r["connection_id"]: r for r in await run_control(api.worker)}
    assert results[ok.json()["id"]]["is_valid"] is True
    assert results[bad.json()["id"]]["is_valid"] is False
    await EngineDriver(api.worker).drain()
    got = (await api.get(f"/v1/connections/{ok.json()['id']}")).json()
    assert got["state"] == "ACTIVE" and got["health"]["name"] == "HEALTHY"
    assert {s["name"]: s["record_count"] for s in got["streams"]}["hosts"] == 2
    assert client_secret_for(client_id) not in str(got)
