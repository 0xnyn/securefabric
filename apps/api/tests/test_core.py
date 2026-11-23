"""M0/M1 API: /v1, problem+json, auth, keys, organizations, catalogue, idempotency, limits."""

import re

import pytest

from securefabric_domain.tenancy import KEY_CACHE

pytestmark = pytest.mark.integration


def is_problem(resp, status: int, code: str) -> None:
    assert resp.status_code == status, resp.text
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == code and body["status"] == status
    assert body["type"].endswith(code) and body["request_id"].startswith("req_")
    assert resp.headers["x-request-id"] == body["request_id"]


async def test_health(api) -> None:
    assert (await api.client.get("/health/live")).json()["status"] == "ok"
    assert (await api.client.get("/health/ready")).json() == {
        "status": "ok",
        "checks": {"database": True},
    }


async def test_authentication_errors_are_problem_json(api) -> None:
    is_problem(await api.client.get("/v1/organizations"), 401, "unauthenticated")
    is_problem(
        await api.get("/v1/organizations", key="sfk_test_us_" + "x" * 43), 401, "invalid_api_key"
    )
    is_problem(
        await api.get("/v1/organizations", key="sfk_test_eu_" + "x" * 43), 401, "wrong_region"
    )
    # Leen clients send X-API-KEY.
    resp = await api.client.get("/v1/organizations", headers={"X-API-KEY": api.key})
    assert resp.status_code == 200


async def test_me_with_api_key(api) -> None:
    me = (await api.get("/v1/me")).json()
    assert me["kind"] == "api_key" and me["environment_id"] == str(api.tenant.environment_id)
    assert "keys:manage" in me["scopes"]


async def test_organizations_crud_search_paging_and_conflict(api) -> None:
    for i in range(5):
        r = await api.post(
            "/v1/organizations", {"identifier": f"cust-{i}", "name": f"Customer {i}"}
        )
        assert r.status_code == 201, r.text
    is_problem(
        await api.post("/v1/organizations", {"identifier": "cust-1", "name": "dup"}),
        409,
        "organization_exists",
    )
    page1 = (await api.get("/v1/organizations", params={"limit": 3})).json()
    assert len(page1["items"]) == 3 and page1["next_cursor"]
    page2 = (
        await api.get("/v1/organizations", params={"limit": 3, "cursor": page1["next_cursor"]})
    ).json()
    assert {o["identifier"] for o in page1["items"]} & {
        o["identifier"] for o in page2["items"]
    } == set()
    assert len(page1["items"]) + len(page2["items"]) == 6  # five plus the harness organization
    back = (
        await api.get("/v1/organizations", params={"limit": 3, "cursor": page2["previous_cursor"]})
    ).json()
    assert [o["id"] for o in back["items"]] == [o["id"] for o in page1["items"]]
    found = (await api.get("/v1/organizations", params={"search": "ustomer 3"})).json()["items"]
    assert [o["identifier"] for o in found] == ["cust-3"]
    is_problem(await api.get("/v1/organizations", params={"bogus": "1"}), 400, "unknown_parameter")
    is_problem(
        await api.get("/v1/organizations", params={"cursor": "tampered.cursor"}),
        400,
        "invalid_cursor",
    )
    is_problem(
        await api.get("/v1/organizations", params={"cursor": page1["next_cursor"], "search": "x"}),
        400,
        "cursor_filter_mismatch",
    )
    org = found[0]
    r = await api.patch(f"/v1/organizations/{org['id']}", {"name": "Renamed"})
    assert r.json()["name"] == "Renamed"
    # TEN-03: 409 while a live connection exists.
    c = await api.post(
        f"/v1/organizations/{org['id']}/connections",
        {"vendor": "SANDBOX", "credentials": {"api_key": "sbx_live_conn"}},
    )
    assert c.status_code == 201, c.text
    is_problem(
        await api.delete(f"/v1/organizations/{org['id']}"), 409, "organization_has_connections"
    )
    assert (await api.delete(f"/v1/connections/{c.json()['id']}")).status_code == 204
    assert (await api.delete(f"/v1/organizations/{org['id']}")).status_code == 204
    is_problem(await api.get(f"/v1/organizations/{org['id']}"), 404, "organization_not_found")


async def test_cross_environment_ids_are_404(api) -> None:
    org = (await api.post("/v1/organizations", {"identifier": "iso", "name": "Iso"})).json()
    is_problem(
        await api.get(f"/v1/organizations/{org['id']}", key=api.other_key),
        404,
        "organization_not_found",
    )
    assert (await api.get("/v1/organizations", key=api.other_key)).json()["items"] == []


async def test_api_keys_shown_once_scoped_and_revocable(api) -> None:
    r = await api.post("/v1/api_keys", {"name": "ci", "scopes": ["provisioning:read"]})
    assert r.status_code == 201
    created = r.json()
    assert created["key"].startswith("sfk_test_us_") and created["prefix"] == created["key"][:16]
    listed = (await api.get("/v1/api_keys")).json()
    assert all("key" not in k for k in listed) and any(k["id"] == created["id"] for k in listed)
    narrow = created["key"]
    assert (await api.get("/v1/organizations", key=narrow)).status_code == 200
    resp = await api.post("/v1/organizations", {"identifier": "x", "name": "x"}, key=narrow)
    is_problem(resp, 403, "scope_missing")
    assert "provisioning:write" in resp.json()["detail"]
    is_problem(await api.post("/v1/api_keys", {"name": "esc"}, key=narrow), 403, "scope_missing")
    assert (await api.delete(f"/v1/api_keys/{created['id']}")).json()["revoked_at"]
    KEY_CACHE.clear()  # other API processes forget within the 30 s cache TTL (revocation < 60 s)
    is_problem(await api.get("/v1/organizations", key=narrow), 401, "invalid_api_key")


async def test_idempotency_keys(api) -> None:
    body = {"identifier": "idem", "name": "Idem"}
    a = await api.post("/v1/organizations", body, headers={"Idempotency-Key": "k1"})
    b = await api.post("/v1/organizations", body, headers={"Idempotency-Key": "k1"})
    assert a.status_code == b.status_code == 201
    assert a.json() == b.json() and b.headers.get("idempotent-replayed") == "true"
    is_problem(
        await api.post(
            "/v1/organizations", {**body, "name": "other"}, headers={"Idempotency-Key": "k1"}
        ),
        422,
        "idempotency_key_reused",
    )


async def test_catalogue_is_public_and_generated_from_manifests(api) -> None:
    connectors = (await api.client.get("/v1/connectors")).json()
    ids = {c["id"] for c in connectors}
    assert {"GITHUB", "SANDBOX"} <= ids
    gh = (await api.client.get("/v1/connectors/GITHUB")).json()
    assert gh["auth"]["connect"] == "redirect" and {s["name"] for s in gh["streams"]} >= {
        "dependabot_alerts",
        "repositories",
    }
    assert any(p["name"] == "Dependabot alerts" for p in gh["permissions"])
    sbx = (await api.client.get("/v1/connectors/SANDBOX")).json()
    assert sbx["credentials_schema"]["properties"]["api_key"]["x-secret"] is True


async def test_integrations(api) -> None:
    r = await api.post(
        "/v1/integrations",
        {
            "connector_id": "SANDBOX",
            "key": "sbx-two",
            "enabled_streams": ["hosts"],
            "stream_intervals": {"hosts": 600},
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["enabled_streams"] == ["hosts"]
    bad = await api.post(
        "/v1/integrations", {"connector_id": "SANDBOX", "key": "bad", "enabled_streams": ["nope"]}
    )
    is_problem(bad, 422, "invalid_integration")
    bad = await api.post(
        "/v1/integrations",
        {"connector_id": "SANDBOX", "key": "bad2", "stream_intervals": {"hosts": 5}},
    )
    is_problem(bad, 422, "invalid_integration")
    listed = (await api.get("/v1/integrations")).json()
    assert any(i["key"] == "sbx-two" for i in listed)


async def test_rate_limit(api) -> None:
    api.client._transport.app.state.rate_limiter.per_minute = 3
    codes = [(await api.get("/v1/me")).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429
    resp = await api.get("/v1/me")
    is_problem(resp, 429, "rate_limited")
    assert int(resp.headers["retry-after"]) >= 1 and resp.headers["x-ratelimit-remaining"] == "0"


async def test_status_runs_under_the_api_role_and_hides_detail_by_audience(api) -> None:
    # Public: the summary only. The API pool is sf_api, which cannot read the migration
    # ledger or the queue tables directly, so a "down" here means the definer function broke.
    public = (await api.client.get("/v1/status")).json()
    assert public["status"] in ("ok", "degraded"), public
    assert public["database"] == {"reachable": True}
    assert public["workers"] == [] and public["queues"] == [] and public["alerts"] == []

    # A customer: workers (no host names or pids), queues, run counts, alert counts only.
    resp = await api.get("/v1/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["database"]["reachable"] is True and body["database"]["server_version"]
    assert "size_bytes" not in body["database"]
    assert "0006_system_status" in body["migrations"]["applied"]
    assert {q["name"] for q in body["queues"]} >= {"sync_interactive", "control", "delivery"}
    assert all("hostname" not in w and "pid" not in w for w in body["workers"])
    assert body["alerts"] == [] and isinstance(body["alert_counts"], dict)

    # Credentials that are sent are checked, as on every route.
    is_problem(await api.get("/v1/status", key="sfk_test_us_" + "x" * 43), 401, "invalid_api_key")


async def test_timestamps_are_iso_utc_with_milliseconds(api) -> None:
    r = await api.post("/v1/organizations", {"identifier": "ts-check", "name": "TS"})
    assert r.status_code == 201, r.text
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", r.json()["created_at"])


async def test_rate_limit_counters_and_api_usage_flush_as_the_api_role(api) -> None:
    # The flush once failed with InsufficientPrivilege under sf_api, silently: usage stayed 0
    # and instances never shared counts. It runs as the API role here.
    from securefabric_api.ratelimit import RateLimiter

    env = api.tenant.environment_id
    before = (await api.get("/v1/usage")).json()["live"]["api_calls_24h"]
    a, b = RateLimiter(api.platform.pool), RateLimiter(api.platform.pool)  # two "instances"
    for _ in range(3):
        assert a.check(env).allowed
    for _ in range(2):
        assert b.check(env).allowed
    await a.sync()
    await b.sync()
    assert b._global[str(env)] >= 5  # b now sees a's calls: limits hold across instances
    after = (await api.get("/v1/usage")).json()["live"]["api_calls_24h"]
    assert after >= before + 5
