"""Write-back: idempotent request → control worker → vendor → re-fetch → our record
reflects what the vendor recorded (ACT-02 round trip, ACT-03)."""

from uuid import UUID

import pytest

from securefabric_connectors.sandbox.vendor import vendor_for
from securefabric_domain.testing import EngineDriver, make_connection, run_control, sync_stream
from securefabric_schema import Mode

pytestmark = pytest.mark.integration
OPTS = {"finding_count": 12}


async def test_set_state_round_trip(api) -> None:
    cid = str(
        await make_connection(
            api.worker, api.tenant, credentials={"api_key": "sbx_action_key"}, options=OPTS
        )
    )
    await sync_stream(api.worker, api.tenant, UUID(cid), "findings", Mode.BACKFILL)
    hdr = {"X-CONNECTION-ID": cid}
    open_f = next(
        f
        for f in (
            await api.get("/v1/vulnerability_findings", headers=hdr, params={"state": "OPEN"})
        ).json()["items"]
    )
    body = {
        "action": "set_state",
        "state": "IGNORED",
        "reason": "accepted_risk",
        "comment": "known",
    }
    r = await api.post(f"/v1/vulnerability_findings/{open_f['id']}/actions", body, headers=hdr)
    assert r.status_code == 400 and r.json()["code"] == "idempotency_key_required"
    a = await api.post(
        f"/v1/vulnerability_findings/{open_f['id']}/actions",
        body,
        headers={**hdr, "Idempotency-Key": "act-1"},
    )
    b = await api.post(
        f"/v1/vulnerability_findings/{open_f['id']}/actions",
        body,
        headers={**hdr, "Idempotency-Key": "act-1"},
    )
    assert (
        a.status_code == 202
        and a.json()["id"] == b.json()["id"]
        and b.headers["idempotent-replayed"] == "true"
    )
    [res] = await run_control(api.worker)
    assert res["ok"], res
    done = (await api.get(f"/v1/actions/{a.json()['id']}")).json()
    assert done["status"] == "SUCCEEDED"
    vendor = vendor_for("sbx_action_key", OPTS)
    assert vendor.findings[open_f["vendor_attributes"]["id"]]["status"] == "suppressed"
    await EngineDriver(api.worker).drain()  # the re-fetch (targeted run)
    after = (await api.get(f"/v1/vulnerability_findings/{open_f['id']}", headers=hdr)).json()
    assert after["state"] == "IGNORED" and after["vendor_attributes"]["data"]["comment"] == "known"
    bad = await api.post(
        f"/v1/vulnerability_findings/{open_f['id']}/actions",
        {"action": "set_state", "state": "CLOSED", "reason": "revoked"},
        headers={**hdr, "Idempotency-Key": "act-2"},
    )
    assert bad.status_code == 422 and bad.json()["code"] == "reason_unsupported"
    narrow = (await api.post("/v1/api_keys", {"name": "ro", "scopes": ["data:read"]})).json()["key"]
    denied = await api.post(
        f"/v1/vulnerability_findings/{open_f['id']}/actions",
        body,
        key=narrow,
        headers={**hdr, "Idempotency-Key": "act-3"},
    )
    assert denied.status_code == 403 and denied.json()["code"] == "scope_missing"
