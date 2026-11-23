"""M5 data API: scopes, every filter, sorts, signed cursors, incremental feed with
deletes, changeType, include, unsupported-filter header, and the Leen V2 contract."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import jsonschema
import pytest

from securefabric_connectors.sandbox.vendor import vendor_for
from securefabric_domain.testing import make_connection, sync_stream
from securefabric_schema import Mode

pytestmark = pytest.mark.integration

LEEN = json.loads(
    (Path(__file__).parents[3] / "packages/schema/tests/leen/openapi_v2.json").read_text()
)
OPTS = {"seed": 3, "finding_count": 48, "host_count": 10, "image_count": 6, "page_size": 20}
KEY = "sbx_data_api_key"


def leen_validator(
    component: str, *, strict_vendor: bool = False
) -> jsonschema.Draft202012Validator:
    """Leen's published schema. Leen's vendor-specific unions (vendor_attributes.data
    keyed by vendor, tag sources) are closed enums of Leen's own vendors; for a vendor
    Leen does not have (SANDBOX) they are relaxed to open objects: our values are
    additive. ``strict_vendor`` keeps them (GITHUB must match Leen's GitHub variant)."""
    comps = json.loads(json.dumps(LEEN["components"]))
    if not strict_vendor:
        comps["schemas"]["VulnerabilityFindingV2VendorAttributes"]["properties"]["data"] = {}
        comps["schemas"]["ResourceVendorAttributes"]["properties"]["data"] = {}
    comps["schemas"]["ResourceTag"]["properties"]["source"] = {"type": "string"}
    return jsonschema.Draft202012Validator(
        {"$ref": f"#/components/schemas/{component}", "components": comps}
    )


def leen_errors(
    component: str, payload: dict[str, Any], *, strict_vendor: bool = False
) -> list[str]:
    return [
        f"{'/'.join(map(str, e.absolute_path))}: {e.message[:200]}"
        for e in leen_validator(component, strict_vendor=strict_vendor).iter_errors(payload)
    ]


async def synced(api) -> str:
    cid = await make_connection(api.worker, api.tenant, credentials={"api_key": KEY}, options=OPTS)
    for s, m in (("hosts", Mode.FULL), ("images", Mode.FULL), ("findings", Mode.BACKFILL)):
        out = await sync_stream(api.worker, api.tenant, cid, s, m)
        assert out.kind == "completed", out.error
    return str(cid)


def scope(cid: str) -> dict[str, str]:
    return {"X-CONNECTION-ID": cid}


async def all_pages(api, path: str, headers: dict[str, str], **params: Any) -> list[dict[str, Any]]:
    items, cursor = [], None
    for _ in range(100):
        q = dict(params)
        if cursor:
            q["cursor"] = cursor
        r = await api.get(path, headers=headers, params=q)
        assert r.status_code == 200, r.text
        body = r.json()
        items += body["items"]
        cursor = body["next_cursor"]
        if not cursor:
            return items
    raise AssertionError("too many pages")


async def test_scope_headers(api) -> None:
    cid = await synced(api)
    r = await api.get("/v1/vulnerability_findings")
    assert r.status_code == 400 and r.json()["code"] == "scope_header_required"
    r = await api.get(
        "/v1/vulnerability_findings",
        headers={**scope(cid), "X-ORGANIZATION-ID": str(api.tenant.organization_id)},
    )
    assert r.status_code == 400
    # Another environment's key cannot see the connection (TEN-02: 404, never 403).
    r = await api.get("/v1/vulnerability_findings", key=api.other_key, headers=scope(cid))
    assert r.status_code == 404
    org = await api.get(
        "/v1/vulnerability_findings", headers={"X-ORGANIZATION-ID": str(api.tenant.organization_id)}
    )
    assert org.status_code == 200


async def test_every_sort_returns_every_row_exactly_once(api) -> None:
    cid = await synced(api)
    for sort in (
        "updated_at:asc",
        "updated_at:desc",
        "severity:desc",
        "severity:asc",
        "state_updated_at:asc",
        "first_seen:desc",
        "last_seen:asc",
    ):
        items = await all_pages(api, "/v1/vulnerability_findings", scope(cid), sort=sort, limit=7)
        ids = [i["id"] for i in items]
        assert len(ids) == len(set(ids)) == 48, sort
    sev = await all_pages(
        api, "/v1/vulnerability_findings", scope(cid), sort="severity:desc", limit=9
    )
    rank = {"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "INFO": 1, "UNKNOWN": 0}
    assert [rank[i["severity"]] for i in sev] == sorted(
        (rank[i["severity"]] for i in sev), reverse=True
    )


async def test_filters(api) -> None:
    cid = await synced(api)
    everything = await all_pages(api, "/v1/vulnerability_findings", scope(cid), limit=500)

    async def q(**params: Any) -> list[dict[str, Any]]:
        return await all_pages(api, "/v1/vulnerability_findings", scope(cid), limit=500, **params)

    crit_high = await q(severity="CRITICAL,HIGH")
    assert crit_high and {i["severity"] for i in crit_high} == {"CRITICAL", "HIGH"}
    assert len(crit_high) == sum(1 for i in everything if i["severity"] in ("CRITICAL", "HIGH"))
    assert {i["state"] for i in await q(state="IGNORED")} == {"IGNORED"}
    assert {i["type"] for i in await q(type="SECRET,CODE")} == {"SECRET", "CODE"}
    assert all(i["has_fix"] is True for i in await q(has_fix="true"))
    assert all(i["exploitable"] is False for i in await q(exploitable="false"))
    nulls = [i for i in everything if i["exploitable"] is None]
    assert nulls and not any(
        i["id"] in {x["id"] for x in nulls}
        for i in await q(exploitable="true") + await q(exploitable="false")
    )
    assert {i["reachability"] for i in await q(reachability="REACHABLE")} == {"REACHABLE"}
    some = everything[:3]
    assert {i["id"] for i in await q(ids=",".join(i["id"] for i in some))} == {
        i["id"] for i in some
    }
    cve = next(i["cve_ids"][0] for i in everything if i["cve_ids"])
    assert all(cve in i["cve_ids"] for i in await q(cveId=cve.lower()))
    res_id = everything[0]["resources"][0]["id"]
    assert all(any(r["id"] == res_id for r in i["resources"]) for i in await q(resourceId=res_id))
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    for p in ("firstSeenSince", "lastSeenSince", "stateUpdatedSince", "updatedSince"):
        assert await q(**{p: future}) == [], p
    for bad, code in (
        ({"exploitable": "null"}, 422),
        ({"severity": "SEVERE"}, 422),
        ({"bogus": "1"}, 400),
        ({"ids": ",".join(["00000000-0000-0000-0000-000000000001"] * 101)}, 422),
        ({"sort": "title:asc"}, 400),
        ({"include": "everything"}, 422),
    ):
        r = await api.get("/v1/vulnerability_findings", headers=scope(cid), params=bad)
        assert r.status_code == code, (bad, r.text)
        assert r.headers["content-type"].startswith("application/problem+json")
    # Resources filters.
    hosts = await all_pages(api, "/v1/resources", scope(cid), type="HOST", limit=500)
    assert len(hosts) == 10 and {h["type"] for h in hosts} == {"HOST"}
    assert {
        r["state"] for r in await all_pages(api, "/v1/resources", scope(cid), state="INACTIVE")
    } <= {"INACTIVE"}
    assert await all_pages(api, "/v1/resources", scope(cid), vendor="GITHUB") == []
    assert len(await all_pages(api, "/v1/resources", scope(cid), vendor="SANDBOX", limit=500)) == 16
    named = hosts[0]["name"]
    assert [r["name"] for r in await all_pages(api, "/v1/resources", scope(cid), name=named)] == [
        named
    ]


async def test_include_resources_embeds_full_objects(api) -> None:
    cid = await synced(api)
    lean = (
        await api.get("/v1/vulnerability_findings", headers=scope(cid), params={"limit": 1})
    ).json()["items"][0]
    full = (
        await api.get(
            "/v1/vulnerability_findings",
            headers=scope(cid),
            params={"limit": 1, "include": "resources"},
        )
    ).json()["items"][0]
    assert "first_seen" not in lean["resources"][0] and "first_seen" in full["resources"][0]
    assert full["resources"][0]["role"] == "primary"


async def test_incremental_feed_with_updates_and_deletes(api) -> None:
    cid = await synced(api)
    first = await all_pages(api, "/v1/vulnerability_findings", scope(cid), limit=500)
    last_cursor = (
        await api.get("/v1/vulnerability_findings", headers=scope(cid), params={"limit": 500})
    ).json()["next_cursor"]
    assert last_cursor is None
    # updatedSince is inclusive (Leen: "at or after"), so start just after the last row.
    mark = (
        datetime.fromisoformat(max(i["updated_at"] for i in first).replace("Z", "+00:00"))
        + timedelta(milliseconds=1)
    ).isoformat()
    vendor = vendor_for(KEY, OPTS)
    changed = vendor.tick()
    gone = sorted(vendor.findings)[10]
    vendor.remove_finding(gone)
    out = await sync_stream(api.worker, api.tenant, UUID(cid), "findings", Mode.INCREMENTAL)
    assert out.kind == "completed", out.error
    feed = await all_pages(
        api, "/v1/vulnerability_findings", scope(cid), updatedSince=mark, limit=2
    )
    by_vendor = {i["vendor_attributes"]["id"]: i for i in feed}
    for fid in changed["closed"] + changed["reopened"] + changed["new"]:
        assert fid in by_vendor, fid
    assert by_vendor[gone]["state"] == "DELETED" and by_vendor[gone]["deleted_at"]
    # A plain listing hides deleted rows; state=DELETED asks for them.
    plain = await all_pages(api, "/v1/vulnerability_findings", scope(cid), limit=500)
    assert gone not in {i["vendor_attributes"]["id"] for i in plain}
    assert [
        i["vendor_attributes"]["id"]
        for i in await all_pages(api, "/v1/vulnerability_findings", scope(cid), state="DELETED")
    ] == [gone]
    # changeType (CDC-03).
    added = await all_pages(
        api, "/v1/vulnerability_findings", scope(cid), updatedSince=mark, changeType="added"
    )
    assert {i["vendor_attributes"]["id"] for i in added} == set(changed["new"])
    deleted = await all_pages(
        api, "/v1/vulnerability_findings", scope(cid), updatedSince=mark, changeType="deleted"
    )
    assert [i["vendor_attributes"]["id"] for i in deleted] == [gone]
    # The same updatedSince alongside a cursor is accepted; a different one is a 400 naming it (API-03).
    r = await api.get(
        "/v1/vulnerability_findings", headers=scope(cid), params={"updatedSince": mark, "limit": 1}
    )
    cur = r.json()["next_cursor"]
    assert (
        await api.get(
            "/v1/vulnerability_findings",
            headers=scope(cid),
            params={"updatedSince": mark, "cursor": cur},
        )
    ).status_code == 200
    bad = await api.get(
        "/v1/vulnerability_findings",
        headers=scope(cid),
        params={"updatedSince": "2020-01-01T00:00:00Z", "cursor": cur},
    )
    assert bad.status_code == 400 and bad.json()["errors"][0]["field"] == "updatedSince"
    # History of a reopened/closed finding.
    hist = (
        await api.get(
            f"/v1/vulnerability_findings/{by_vendor[changed['closed'][0]]['id']}/history",
            headers=scope(cid),
        )
    ).json()
    assert hist[-1]["to_state"] == "CLOSED"


async def test_organization_scope_merges_connections_and_hides_fresh_rows(api) -> None:
    a = await synced(api)
    b = await make_connection(
        api.worker, api.tenant, credentials={"api_key": "sbx_second_conn"}, options=OPTS
    )
    await sync_stream(api.worker, api.tenant, b, "findings", Mode.BACKFILL)
    org = {"X-ORGANIZATION-ID": str(api.tenant.organization_id)}
    fresh = await all_pages(api, "/v1/vulnerability_findings", org, limit=500)
    assert fresh == []  # younger than 5 seconds (part 4, section 7)
    from securefabric_db import tenant_tx

    async with tenant_tx(api.worker.pool, api.tenant.environment_id) as conn:
        await conn.execute(
            "update data.vulnerability_finding set updated_at = updated_at - interval '10 seconds' "
            "where connection_id = any(%s)",
            ([a, str(b)],),
        )
    merged = await all_pages(api, "/v1/vulnerability_findings", org, limit=500)
    assert {i["connection_id"] for i in merged} == {a, str(b)} and len(merged) == 96
    only_b = await all_pages(api, "/v1/vulnerability_findings", org, connectionId=str(b), limit=500)
    assert {i["connection_id"] for i in only_b} == {str(b)}


async def test_unsupported_filter_header(api) -> None:
    from securefabric_domain.testing import make_connection as mk

    gh = await mk(api.worker, api.tenant, "GITHUB", config={"installation_id": 1})
    r = await api.get(
        "/v1/vulnerability_findings", headers=scope(str(gh)), params={"exploitable": "true"}
    )
    assert r.status_code == 200 and r.headers["x-unsupported-filters"] == "exploitable"
    sbx = await synced(api)
    r = await api.get(
        "/v1/vulnerability_findings", headers=scope(sbx), params={"exploitable": "true"}
    )
    assert "x-unsupported-filters" not in r.headers


async def test_leen_v2_contract(api) -> None:
    """Every finding and resource we return validates against Leen's published V2 schema."""
    cid = await synced(api)
    findings = await all_pages(
        api, "/v1/vulnerability_findings", scope(cid), limit=500, include="resources"
    )
    problems = {i["id"]: leen_errors("VulnerabilityFindingV2RespModel", i) for i in findings}
    problems = {k: v for k, v in problems.items() if v}
    assert not problems, json.dumps(list(problems.values())[:3], indent=1)
    resources = await all_pages(api, "/v1/resources", scope(cid), limit=500)
    problems = {r["id"]: leen_errors("ResourceRespModel", r) for r in resources}
    problems = {k: v for k, v in problems.items() if v}
    assert not problems, json.dumps(list(problems.values())[:3], indent=1)
    one = (
        await api.get(f"/v1/vulnerability_findings/{findings[0]['id']}", headers=scope(cid))
    ).json()
    assert not leen_errors("VulnerabilityFindingV2RespModel", one)


async def test_a_leen_v2_client_works_after_the_migration_guide_changes(api) -> None:
    """M10 exit: a Leen client with only the docs/guides/leen-migration.md changes applied
    (base path /v1, an sfk_ key in X-API-KEY, new connection ids) pages through findings
    and resources with Leen's own query parameters, and every response validates against
    Leen's published schema."""
    cid = await synced(api)
    leen_headers = {"X-API-KEY": api.key, "X-CONNECTION-ID": cid}  # header names unchanged
    envelope = {"items", "next_cursor", "previous_cursor"}  # Leen's pagination envelope

    # Leen query parameters, verbatim: sort, multi-value filters, tri-state, limit.
    params = {
        "sort": "severity:desc",
        "severity": "CRITICAL,HIGH,MEDIUM,LOW",
        "state": "OPEN,CLOSED,IGNORED",
        "has_fix": "true",
        "limit": "25",
    }
    seen: list[str] = []
    cursor = None
    for _ in range(50):
        r = await api.client.get(
            "/v1/vulnerability_findings",
            params={**params, **({"cursor": cursor} if cursor else {})},
            headers=leen_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert envelope <= body.keys()
        assert not {
            f["id"]: e
            for f in body["items"]
            if (e := leen_errors("VulnerabilityFindingV2RespModel", f))
        }
        seen.extend(f["id"] for f in body["items"])
        assert all(f["has_fix"] is True for f in body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert seen and len(seen) == len(set(seen))  # every row once, no duplicates
    r = await api.client.get(f"/v1/vulnerability_findings/{seen[0]}", headers=leen_headers)
    assert r.status_code == 200

    r = await api.client.get(
        "/v1/resources", params={"state": "ACTIVE", "limit": "50"}, headers=leen_headers
    )
    assert r.status_code == 200, r.text
    assert envelope <= r.json().keys()
    assert not {x["id"]: e for x in r.json()["items"] if (e := leen_errors("ResourceRespModel", x))}
    # Leen's 422 for a null tri-state filter holds here too.
    bad = await api.client.get(
        "/v1/vulnerability_findings", params={"has_fix": "null"}, headers=leen_headers
    )
    assert bad.status_code == 422
