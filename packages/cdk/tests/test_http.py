"""HTTP client classification, retries, rate limits, auth refresh, egress, capture."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2
import pytest

from securefabric_cdk.egress import EgressTransport, check_url, resolve_checked
from securefabric_cdk.errors import (
    AuthRejected,
    EgressDenied,
    FeatureNotEnabled,
    PermissionMissing,
    RateLimited,
    VendorRejected,
    VendorUnavailable,
)
from securefabric_cdk.http import HttpClient, MemoryOpLog, scrub_body
from securefabric_cdk.manifest import BodyPattern, HttpSpec, RetrySpec
from securefabric_cdk.paginate import link_header_pages, offset_pages, parse_link_header
from securefabric_cdk.tokens import CachedToken, ExchangeProvider, MemoryCredentialStore
from securefabric_cdk.types import AuthMaterial
from securefabric_core.clock import FrozenClock

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

GITHUB_LIKE = HttpSpec(
    retry=RetrySpec(
        statuses=[429, "5xx"],
        reset_header="x-ratelimit-reset",
        retry_after_header="retry-after",
        remaining_header="x-ratelimit-remaining",
        limit_header="x-ratelimit-limit",
        body_patterns=[
            BodyPattern(status=403, contains="secondary rate limit", treat_as="rate_limited"),
            BodyPattern(
                status=403,
                contains="Advanced Security must be enabled",
                treat_as="feature_not_enabled",
            ),
            BodyPattern(
                status=403,
                contains="Resource not accessible by integration",
                treat_as="permission_missing",
            ),
        ],
    )
)


class Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, s: float) -> None:
        self.calls.append(s)


def client(
    handler: Any,
    *,
    auth: Any = None,
    capture: Any = None,
    spec: HttpSpec = GITHUB_LIKE,
    sleeps: Sleeps | None = None,
    log: MemoryOpLog | None = None,
) -> HttpClient:
    return HttpClient(
        base_url="https://api.example.test",
        transport=httpx2.MockTransport(handler),
        spec=spec,
        auth=auth,
        capture=capture,
        clock=FrozenClock(NOW),
        sleep=sleeps or Sleeps(),
        log=log,
        scrub_fields=("secret",),
        stream="dependabot_alerts",
    )


def seq(*responses: httpx2.Response) -> Any:
    it = iter(responses)
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return next(it)

    handler.seen = seen  # type: ignore[attr-defined]
    return handler


async def test_success_captures_scrubbed_body_and_logs() -> None:
    captured: list[tuple[dict[str, Any], bytes]] = []

    class Cap:
        async def capture(self, *, request_summary: dict[str, Any], body: bytes) -> str | None:
            captured.append((request_summary, body))
            return "raw-1"

    log = MemoryOpLog()
    c = client(
        seq(
            httpx2.Response(200, json=[{"number": 1, "secret": "ghp_x", "nested": {"secret": "y"}}])
        ),
        capture=Cap(),
        log=log,
    )
    resp = await c.request("GET", "/repos/1/alerts/2")
    assert resp.status_code == 200
    assert json.loads(captured[0][1]) == [{"number": 1, "nested": {}}]
    assert captured[0][0]["path"] == "/repos/{id}/alerts/{id}"
    assert log.lines[0]["status"] == 200
    assert c.vendor_requests == 1


async def test_5xx_retries_then_fails_as_vendor_unavailable() -> None:
    sleeps = Sleeps()
    h = seq(*[httpx2.Response(502)] * 4)
    with pytest.raises(VendorUnavailable):
        await client(h, sleeps=sleeps).request("GET", "/x")
    assert len(h.seen) == 4  # first try + 3 in-request retries
    assert len(sleeps.calls) == 3


async def test_5xx_then_success() -> None:
    resp = await client(seq(httpx2.Response(503), httpx2.Response(200, json={}))).request(
        "GET", "/x"
    )
    assert resp.status_code == 200


async def test_network_error_retries() -> None:
    calls = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx2.ConnectError("refused")
        return httpx2.Response(200, json={})

    assert (await client(handler).request("GET", "/x")).status_code == 200


async def test_short_rate_limit_sleeps_in_process() -> None:
    sleeps = Sleeps()
    h = seq(httpx2.Response(429, headers={"retry-after": "30"}), httpx2.Response(200, json={}))
    assert (await client(h, sleeps=sleeps).request("GET", "/x")).status_code == 200
    assert sleeps.calls == [30.0]


async def test_long_rate_limit_parks() -> None:
    reset = int((NOW + timedelta(minutes=20)).timestamp())
    h = seq(
        httpx2.Response(
            403,
            headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)},
            json={"message": "API rate limit exceeded"},
        )
    )
    with pytest.raises(RateLimited) as exc:
        await client(h).request("GET", "/x")
    assert exc.value.reset_at == NOW + timedelta(minutes=20)


async def test_secondary_rate_limit_body_is_not_a_permission_error() -> None:
    sleeps = Sleeps()
    h = seq(
        httpx2.Response(403, json={"message": "You have exceeded a secondary rate limit"}),
        httpx2.Response(200, json={}),
    )
    await client(h, sleeps=sleeps).request("GET", "/x")
    assert sleeps.calls == [60.0]


async def test_body_patterns_classify_403s() -> None:
    with pytest.raises(FeatureNotEnabled):
        await client(
            seq(
                httpx2.Response(
                    403, json={"message": "Advanced Security must be enabled for this repository"}
                )
            )
        ).request("GET", "/x")
    with pytest.raises(PermissionMissing) as exc:
        await client(
            seq(httpx2.Response(403, json={"message": "Resource not accessible by integration"}))
        ).request("GET", "/x")
    assert exc.value.stream == "dependabot_alerts"
    with pytest.raises(VendorRejected) as rej:
        await client(seq(httpx2.Response(403, json={"message": "Forbidden"}))).request("GET", "/x")
    assert rej.value.status == 403


async def test_allow_returns_status_instead_of_raising() -> None:
    resp = await client(seq(httpx2.Response(404, json={}))).request("GET", "/x", allow=(404,))
    assert resp.status_code == 404
    with pytest.raises(VendorRejected):
        await client(seq(httpx2.Response(404, json={}))).request("GET", "/x")


class FlakyAuth:
    def __init__(self, rotate: bool) -> None:
        self.rotate = rotate
        self.forced = 0

    async def material(
        self, scheme: str = "default", *, force_refresh: bool = False
    ) -> AuthMaterial:
        if force_refresh:
            self.forced += 1
        token = f"t{self.forced}" if self.rotate else "t0"
        return AuthMaterial(headers={"Authorization": f"Bearer {token}"}, fingerprint=token)


async def test_401_retries_once_when_refresh_yields_new_token() -> None:
    auth = FlakyAuth(rotate=True)
    h = seq(httpx2.Response(401), httpx2.Response(200, json={}))
    assert (await client(h, auth=auth).request("GET", "/x")).status_code == 200
    assert h.seen[1].headers["authorization"] == "Bearer t1"


async def test_401_with_same_token_after_refresh_is_auth_rejected() -> None:
    auth = FlakyAuth(rotate=False)
    with pytest.raises(AuthRejected):
        await client(seq(httpx2.Response(401), httpx2.Response(401)), auth=auth).request(
            "GET", "/x"
        )


async def test_401_twice_does_not_loop() -> None:
    auth = FlakyAuth(rotate=True)
    with pytest.raises(AuthRejected):
        await client(seq(httpx2.Response(401), httpx2.Response(401)), auth=auth).request(
            "GET", "/x"
        )


def test_scrub_body_drops_fields() -> None:
    assert json.loads(
        scrub_body(b'{"a":1,"secret":"s","b":[{"secret":2}]}', frozenset({"secret"}))
    ) == {"a": 1, "b": [{}]}
    assert scrub_body(b"not json", frozenset({"secret"})) == b"not json"


# ---------------------------------------------------------------- pagination


def test_parse_link_header() -> None:
    v = '<https://api.github.com/x?page=2>; rel="next", <https://api.github.com/x?page=5>; rel="last"'
    assert parse_link_header(v) == {
        "next": "https://api.github.com/x?page=2",
        "last": "https://api.github.com/x?page=5",
    }


async def test_link_header_pages_and_resume() -> None:
    pages = {
        None: (["a", "b"], '<https://api.example.test/items?after=2>; rel="next"'),
        "2": (["c"], None),
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        after = request.url.params.get("after")
        items, link = pages[after]
        return httpx2.Response(200, json=items, headers={"link": link} if link else {})

    c = client(handler)
    got = [
        (p.items, p.resume) async for p in link_header_pages(c, "/items", params={"per_page": 2})
    ]
    assert got == [(["a", "b"], "https://api.example.test/items?after=2"), (["c"], None)]
    resumed = [p.items async for p in link_header_pages(c, "/items", resume_url=got[0][1])]
    assert resumed == [["c"]]


async def test_offset_pages() -> None:
    data = list(range(7))

    def handler(request: httpx2.Request) -> httpx2.Response:
        off, lim = int(request.url.params["offset"]), int(request.url.params["limit"])
        return httpx2.Response(200, json={"items": data[off : off + lim], "total": len(data)})

    got = [(p.items, p.resume) async for p in offset_pages(client(handler), "/x", limit=3)]
    assert got == [([0, 1, 2], 3), ([3, 4, 5], 6), ([6], None)]


# ---------------------------------------------------------------- egress


async def test_egress_rejects_private_and_metadata() -> None:
    for host in (
        "127.0.0.1",
        "10.1.2.3",
        "169.254.169.254",
        "192.168.1.1",
        "100.64.0.1",
        "::1",
        "fd00::1",
        "metadata.google.internal",
    ):
        with pytest.raises(EgressDenied):
            await resolve_checked(host, 443)
    with pytest.raises(EgressDenied):
        await check_url("http://user:pw@example.com/")
    with pytest.raises(EgressDenied):
        await check_url("http://example.com/", require_https=True)
    assert await resolve_checked("127.0.0.1", 443, allow_private=True) == ["127.0.0.1"]


async def test_egress_transport_pins_and_checks_redirects() -> None:
    seen: list[httpx2.Request] = []

    class Inner(httpx2.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
            seen.append(request)
            if request.url.path == "/start":
                return httpx2.Response(
                    302, headers={"location": "http://169.254.169.254/latest"}, request=request
                )
            return httpx2.Response(200, request=request)

    transport = EgressTransport(Inner())
    async with httpx2.AsyncClient(transport=transport, follow_redirects=True) as c:
        with pytest.raises(EgressDenied):
            await c.get("http://1.1.1.1/start")
    assert len(seen) == 1


# ---------------------------------------------------------------- token providers


async def test_fifty_concurrent_readers_cause_one_refresh() -> None:
    clock = FrozenClock(NOW)
    store = MemoryCredentialStore(clock)
    calls = {"n": 0}

    async def exchange(current: CachedToken | None) -> CachedToken:
        calls["n"] += 1
        await asyncio.sleep(0.01)
        return CachedToken(
            access_token=f"tok{calls['n']}", expires_at=clock.now() + timedelta(hours=1)
        )

    provider = ExchangeProvider(
        store, {"default": exchange}, clock=clock, margin=timedelta(minutes=10)
    )
    results = await asyncio.gather(*[provider.material() for _ in range(50)])
    assert calls["n"] == 1
    assert {r.fingerprint for r in results} == {results[0].fingerprint}

    # Expiring soon: the next reader refreshes once more.
    clock.advance(minutes=55)
    await asyncio.gather(*[provider.material() for _ in range(20)])
    assert calls["n"] == 2


async def test_concurrent_forced_refreshes_collapse() -> None:
    clock = FrozenClock(NOW)
    store = MemoryCredentialStore(clock)
    calls = {"n": 0}

    async def exchange(current: CachedToken | None) -> CachedToken:
        calls["n"] += 1
        await asyncio.sleep(0.01)
        return CachedToken(
            access_token=f"tok{calls['n']}", expires_at=clock.now() + timedelta(hours=1)
        )

    provider = ExchangeProvider(
        store, {"default": exchange}, clock=clock, margin=timedelta(minutes=10)
    )
    await provider.material()
    await asyncio.gather(*[provider.material(force_refresh=True) for _ in range(10)])
    assert calls["n"] == 2


async def test_refresh_failure_policy() -> None:
    clock = FrozenClock(NOW)
    store = MemoryCredentialStore(clock)

    async def exchange(current: CachedToken | None) -> CachedToken:
        raise AuthRejected("invalid_grant")

    provider = ExchangeProvider(store, {"default": exchange}, clock=clock)
    with pytest.raises(AuthRejected):
        await provider.material()
    # Within 30 s of a failure, no new vendor call is made.
    with pytest.raises(VendorUnavailable):
        await provider.material()
    # Failing on 4 distinct calendar days exhausts the credential (AUTH-06).
    from securefabric_cdk.errors import ReauthorizationRequired

    for _ in range(2):
        clock.advance(days=1)
        with pytest.raises(AuthRejected):
            await provider.material()
    clock.advance(days=1)
    with pytest.raises(ReauthorizationRequired):
        await provider.material()
    clock.advance(days=1)
    with pytest.raises(ReauthorizationRequired):
        await provider.material()


async def test_recording_transport_passes_on_compressed_responses() -> None:
    """Real vendors gzip their bodies; the recorder must hand the client a body it can read
    (found live against GitHub: the decoded body was re-sent with Content-Encoding: gzip)."""
    import gzip
    import json

    import httpx2

    from securefabric_cdk.fixtures import RecordingTransport

    payload = [{"id": 1, "name": "repo"}]

    class GzipVendor(httpx2.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(
                200,
                headers={"content-encoding": "gzip", "content-type": "application/json"},
                content=gzip.compress(json.dumps(payload).encode()),
                request=request,
            )

    rec = RecordingTransport(GzipVendor())
    async with httpx2.AsyncClient(transport=rec, base_url="https://vendor.example") as c:
        r = await c.get("/repos")
    assert r.json() == payload
    assert rec.interactions[0].body == payload
