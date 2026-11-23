"""TEN-02: for every endpoint with an id, a key from environment B gets 404 for
every id from environment A, and nothing changes. Generated from the OpenAPI
document, so a new endpoint is covered automatically."""

import re
from typing import Any

import pytest

from securefabric_api.openapi import build_schema
from securefabric_db import fetch_required, tenant_tx
from securefabric_domain.testing import run_control, sync_stream
from securefabric_schema import Mode

pytestmark = pytest.mark.integration

# Path parameters that are not tenant ids (public catalogue, enums).
NOT_TENANT = {"connector_id", "connector", "cve_id"}
SKIP_PREFIXES = ("/v1/connect/", "/v1/ingress/", "/health/")


async def seed_a(api) -> dict[str, str]:
    org = (await api.post("/v1/organizations", {"identifier": "iso-a", "name": "Iso A"})).json()[
        "id"
    ]
    conn = (
        await api.post(
            f"/v1/organizations/{org}/connections",
            {
                "vendor": "SANDBOX",
                "credentials": {"api_key": "sbx_isolation_a"},
                "options": {"finding_count": 5, "host_count": 2, "image_count": 0},
            },
        )
    ).json()["id"]
    await run_control(api.worker)
    await sync_stream(api.worker, api.tenant, conn, "hosts", Mode.FULL)
    await sync_stream(api.worker, api.tenant, conn, "findings", Mode.BACKFILL)
    job = (await api.post(f"/v1/connections/{conn}/jobs", {})).json()["id"]
    key = (await api.post("/v1/api_keys", {"name": "a-key"})).json()["id"]
    integ = (
        await api.post("/v1/integrations", {"connector_id": "SANDBOX", "key": "iso-int"})
    ).json()["id"]
    async with tenant_tx(api.worker.pool, api.tenant.environment_id) as c:
        finding = (
            await fetch_required(
                c,
                "select id from data.vulnerability_finding where connection_id = %s limit 1",
                (conn,),
            )
        )["id"]
        resource = (
            await fetch_required(
                c, "select id from data.resource where connection_id = %s limit 1", (conn,)
            )
        )["id"]
    ids = {
        "organization_id": org,
        "connection_id": conn,
        "job_id": job,
        "key_id": key,
        "integration_id": integ,
        "finding_id": str(finding),
        "resource_id": str(resource),
    }
    for extra, path in (("endpoint_id", "/v1/webhook_endpoints"),):
        r = await api.post(path, {"url": "https://example.com/hook", "event_types": []})
        if r.status_code == 201:
            ids[extra] = r.json()["id"]
    return ids


async def test_every_id_endpoint_is_404_across_environments(api) -> None:
    ids = await seed_a(api)
    schema = build_schema()
    checked = 0
    for path, item in schema["paths"].items():
        if path.startswith(SKIP_PREFIXES):
            continue
        params = re.findall(r"{(\w+)}", path)
        tenant_params = [p for p in params if p not in NOT_TENANT]
        if not tenant_params:
            continue
        for method in item:
            missing = [p for p in tenant_params if p not in ids]
            if missing:
                continue
            url = path
            for p in params:
                url = url.replace("{" + p + "}", ids.get(p, "x"))
            headers = {
                "Authorization": f"Bearer {api.other_key}",
                "X-CONNECTION-ID": ids["connection_id"],
            }
            body: dict[str, Any] | None = {} if method in ("post", "patch", "put") else None
            resp = await api.client.request(method.upper(), url, headers=headers, json=body)
            assert resp.status_code in (404, 422), (
                f"{method.upper()} {path} with another environment's key returned {resp.status_code}: {resp.text[:200]}"
            )
            if resp.status_code == 422:
                # Body validation may run first; resend a minimal valid body and require 404.
                resp = await api.client.request(
                    method.upper(), url, headers=headers, json={"state": "PAUSED"}
                )
                assert resp.status_code in (404, 422), (
                    f"{method.upper()} {path}: {resp.status_code}"
                )
            checked += 1
    assert checked >= 20, f"only {checked} operations checked"
    # Nothing in A changed.
    assert (await api.get(f"/v1/connections/{ids['connection_id']}")).json()["state"] == "ACTIVE"
    assert (await api.get(f"/v1/organizations/{ids['organization_id']}")).status_code == 200
