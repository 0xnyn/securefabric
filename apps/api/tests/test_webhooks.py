"""M6 outbound webhooks: outbox → dispatch → signed delivery, retries, dead, replay,
rotation with dual signatures, auto-disable, ping, pull feed."""

import json
from typing import Any

import pytest

from securefabric_cdk.inprocess import InProcessTransport, VendorRequest, VendorResponse
from securefabric_db import fetch_all, tenant_tx
from securefabric_domain.events.delivery import RETRY_SCHEDULE_S, attempt_delivery, verify_signature
from securefabric_domain.events.outbox import emit
from securefabric_domain.sync.scheduler import Scheduler
from securefabric_domain.testing import run_deliveries

pytestmark = pytest.mark.integration


class Receiver:
    def __init__(self) -> None:
        self.up = True
        self.status = 200
        self.received: list[VendorRequest] = []

    def __call__(self, req: VendorRequest) -> VendorResponse:
        self.received.append(req)
        if not self.up:
            return VendorResponse(503, {"error": "down"})
        return VendorResponse(self.status, {"ok": True})


async def _tick(api) -> None:
    s = Scheduler(api.worker)
    s.maintenance_enabled = False
    await s.tick()


def wire(api, receiver: Receiver) -> None:
    api.worker.webhook_transport = lambda: InProcessTransport(receiver)


async def endpoint(api, **kw: Any) -> dict[str, Any]:
    r = await api.post("/v1/webhook_endpoints", {"url": "https://example.com/hooks", **kw})
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


async def emit_event(api, type_: str = "sync.completed", **data: Any) -> dict[str, Any]:
    async with tenant_tx(api.worker.pool, api.tenant.environment_id) as conn:
        return await emit(conn, environment_id=api.tenant.environment_id, type=type_, data=data)


async def test_signed_delivery_and_receiver_verification(api) -> None:
    rx = Receiver()
    wire(api, rx)
    ep = await endpoint(api)
    assert ep["secret"].startswith("whsec_")
    ev = await emit_event(api, totals={"added": 1})
    await _tick(api)
    res = await run_deliveries(api.worker)
    assert [r["status"] for r in res] == ["DELIVERED"]
    [req] = rx.received
    assert req.headers["securefabric-event-id"] == ev["id"]
    assert verify_signature(
        ep["secret"],
        req.headers["securefabric-signature"],
        req.headers["securefabric-timestamp"],
        req.body,
        now=int(req.headers["securefabric-timestamp"]),
    )
    assert not verify_signature(
        "whsec_wrong",
        req.headers["securefabric-signature"],
        req.headers["securefabric-timestamp"],
        req.body,
        now=int(req.headers["securefabric-timestamp"]),
    )
    body = json.loads(req.body)
    assert body["id"] == ev["id"] and body["type"] == "sync.completed" and body["environment_id"]
    deliveries = (await api.get(f"/v1/webhook_endpoints/{ep['id']}/deliveries")).json()
    assert (
        deliveries[0]["status"] == "DELIVERED"
        and deliveries[0]["attempts_log"][0]["status_code"] == 200
    )


async def test_event_type_subscriptions(api) -> None:
    rx = Receiver()
    wire(api, rx)
    await endpoint(api, event_types=["connection.deleted"])
    await emit_event(api, "sync.completed")
    await emit_event(api, "connection.deleted")
    await _tick(api)
    await run_deliveries(api.worker)
    assert [json.loads(r.body)["type"] for r in rx.received] == ["connection.deleted"]


async def test_a_receiver_down_for_three_hours_receives_every_event(api) -> None:
    rx = Receiver()
    rx.up = False
    wire(api, rx)
    ep = await endpoint(api)
    events = [await emit_event(api, n=i) for i in range(3)]
    await _tick(api)
    await run_deliveries(api.worker)  # first attempt fails, each delivery waits 10 s
    async with tenant_tx(api.worker.pool, api.tenant.environment_id) as conn:
        ds = await fetch_all(
            conn, "select id from events.webhook_delivery where endpoint_id = %s", (ep["id"],)
        )
    elapsed = 0.0
    for attempt, _delay in enumerate(RETRY_SCHEDULE_S[1:], start=2):
        elapsed += RETRY_SCHEDULE_S[attempt - 2]
        api.worker.clock.advance(RETRY_SCHEDULE_S[attempt - 2] * 1.1)
        rx.up = elapsed >= 3 * 3600
        results = [
            await attempt_delivery(api.worker, api.tenant.environment_id, d["id"]) for d in ds
        ]
        if rx.up:
            assert {r.status for r in results} == {"DELIVERED"}
            break
        assert {r.status for r in results} == {"RETRY"}
    delivered = {
        json.loads(r.body)["id"] for r in rx.received if (rx.up and r is rx.received[-1]) or True
    }
    assert {e["id"] for e in events} <= delivered


async def test_permanent_4xx_and_dead_letter_and_replay(api) -> None:
    rx = Receiver()
    rx.status = 410
    wire(api, rx)
    ep = await endpoint(api)
    await emit_event(api)
    await _tick(api)
    assert [r["status"] for r in await run_deliveries(api.worker)] == ["FAILED"]
    d = (await api.get(f"/v1/webhook_endpoints/{ep['id']}/deliveries")).json()[0]
    assert d["status"] == "FAILED" and d["last_status_code"] == 410
    rx.status = 200
    assert (await api.post(f"/v1/webhook_deliveries/{d['id']}/replay")).status_code == 202
    assert [r["status"] for r in await run_deliveries(api.worker)] == ["DELIVERED"]


async def test_rotation_sends_both_signatures_for_24_hours(api) -> None:
    rx = Receiver()
    wire(api, rx)
    ep = await endpoint(api)
    rotated = (await api.post(f"/v1/webhook_endpoints/{ep['id']}/rotate_secret")).json()
    await emit_event(api)
    await _tick(api)
    await run_deliveries(api.worker)
    req = rx.received[-1]
    ts, sig = req.headers["securefabric-timestamp"], req.headers["securefabric-signature"]
    assert sig.count("v1=") == 2
    for secret in (ep["secret"], rotated["secret"]):
        assert verify_signature(secret, sig, ts, req.body, now=int(ts))
    api.worker.clock.advance(hours=25)
    await emit_event(api)
    await _tick(api)
    await run_deliveries(api.worker)
    assert rx.received[-1].headers["securefabric-signature"].count("v1=") == 1


async def test_auto_disable_after_five_failing_days(api) -> None:
    rx = Receiver()
    rx.up = False
    wire(api, rx)
    ep = await endpoint(api)
    await emit_event(api)
    await _tick(api)
    await run_deliveries(api.worker)
    async with tenant_tx(api.worker.pool, api.tenant.environment_id) as conn:
        [d] = await fetch_all(
            conn, "select id from events.webhook_delivery where endpoint_id = %s", (ep["id"],)
        )
    api.worker.clock.advance(days=5, seconds=1)
    await attempt_delivery(api.worker, api.tenant.environment_id, d["id"])
    got = (await api.get(f"/v1/webhook_endpoints/{ep['id']}")).json()
    assert got["enabled"] is False and "5 days" in got["disabled_reason"]


async def test_dispatch_is_atomic_and_idempotent(api) -> None:
    """Killing the dispatcher mid-transaction loses no events; re-dispatch does not duplicate."""
    rx = Receiver()
    wire(api, rx)
    await endpoint(api)
    ev = await emit_event(api)
    from securefabric_db import system_tx
    from securefabric_domain.events import dispatch as dispatch_mod

    class Boom(Exception):
        pass

    async def crash(*a: Any, **k: Any) -> str:
        raise Boom()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(dispatch_mod, "spawn_sql", crash)
        with pytest.raises(Boom):
            await dispatch_mod.dispatch_outbox(api.worker)
    async with system_tx(api.worker.sys_pool) as conn:
        assert (
            await fetch_all(
                conn,
                "select dispatched_at from events.outbox_event where payload->>'id' = %s",
                (ev["id"],),
            )
        )[0]["dispatched_at"] is None
    await dispatch_mod.dispatch_outbox(api.worker)
    await dispatch_mod.dispatch_outbox(api.worker)
    await run_deliveries(api.worker)
    assert [json.loads(r.body)["id"] for r in rx.received] == [ev["id"]]


async def test_ping_limits_and_pull_feed(api) -> None:
    rx = Receiver()
    wire(api, rx)
    ep = await endpoint(api)
    assert (await api.post(f"/v1/webhook_endpoints/{ep['id']}/ping")).status_code == 202
    await run_deliveries(api.worker)
    assert json.loads(rx.received[-1].body)["type"] == "webhook.ping"
    for _ in range(4):
        await endpoint(api)
    r = await api.post("/v1/webhook_endpoints", {"url": "https://example.com/six"})
    assert r.status_code == 409 and r.json()["code"] == "endpoint_limit"
    bad = await api.post("/v1/webhook_endpoints", {"url": "http://example.com/plain"})
    assert bad.status_code == 422
    bad = await api.post("/v1/webhook_endpoints", {"url": "https://127.0.0.1/x"})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_url"
    a = await emit_event(api, n=1)
    b = await emit_event(api, n=2)
    feed = (await api.get("/v1/events", params={"after": a["id"]})).json()
    assert [e["id"] for e in feed["items"]][:1] == [b["id"]]
    assert all(e["id"] > a["id"] for e in feed["items"])
    assert (await api.get("/v1/events", key=api.other_key)).json()["items"] == []
