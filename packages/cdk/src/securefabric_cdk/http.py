"""The one HTTP client (docs/plan/04-sync-engine.md, section 6).

Everything a connector does to the outside world goes through here: auth
injection, base URL, rate budget, the declared retry policy, egress policy, raw
capture and operation-log lines. No connector implements any of it.

Ports (implemented by the platform, faked in tests):

- :class:`AuthInjector` supplies auth headers and can force a refresh (RATE-05)
- :class:`RateBudget` leases tokens before a request and learns from headers (RATE-03/04)
- :class:`RawCapture` archives each successful response body before parsing (STORE-10)
- :class:`OpLog` writes customer-visible operation lines (OBS-01)
"""

import asyncio
import json
import random
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx2

from securefabric_cdk.errors import (
    AuthRejected,
    FeatureNotEnabled,
    PermissionMissing,
    RateLimited,
    VendorRejected,
    VendorUnavailable,
)
from securefabric_cdk.manifest import HttpSpec
from securefabric_cdk.types import AuthMaterial
from securefabric_core.clock import SYSTEM_CLOCK, Clock
from securefabric_core.telemetry import instruments, status_class

PARK_THRESHOLD_S = 120.0  # waits longer than this park the run (RATE-02)
_MAX_RATE_SLEEPS = 5


# ---------------------------------------------------------------- ports


class AuthInjector(Protocol):
    async def material(
        self, scheme: str = "default", *, force_refresh: bool = False
    ) -> AuthMaterial: ...


class RateBudget(Protocol):
    async def acquire(self, cost: int, *, interactive: bool) -> None: ...

    async def observe(
        self, *, remaining: int | None, limit: int | None, reset_at: datetime | None
    ) -> None: ...


class RawCapture(Protocol):
    async def capture(self, *, request_summary: dict[str, Any], body: bytes) -> str | None: ...


class OpLog(Protocol):
    def log(self, level: str, message: str, **fields: Any) -> None: ...

    def http(self, entry: dict[str, Any]) -> None: ...


class NullBudget:
    async def acquire(self, cost: int, *, interactive: bool) -> None:
        return None

    async def observe(
        self, *, remaining: int | None, limit: int | None, reset_at: datetime | None
    ) -> None:
        return None


@dataclass
class MemoryOpLog:
    lines: list[dict[str, Any]] = field(default_factory=list)

    def log(self, level: str, message: str, **fields: Any) -> None:
        self.lines.append({"kind": "log", "level": level, "message": message, **fields})

    def http(self, entry: dict[str, Any]) -> None:
        self.lines.append({"kind": "http", **entry})


# ---------------------------------------------------------------- helpers


def scrub_json(value: Any, fields: frozenset[str]) -> Any:
    """Drop connector-declared sensitive fields (e.g. GitHub's ``secret``) everywhere."""
    if isinstance(value, dict):
        return {k: scrub_json(v, fields) for k, v in value.items() if k not in fields}
    if isinstance(value, list):
        return [scrub_json(v, fields) for v in value]
    return value


def scrub_body(body: bytes, fields: frozenset[str]) -> bytes:
    if not fields or not body:
        return body
    try:
        parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return body
    return json.dumps(scrub_json(parsed, fields), separators=(",", ":")).encode()


def _header_int(headers: Mapping[str, str], name: str | None) -> int | None:
    if not name:
        return None
    raw = headers.get(name)
    if raw is None:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _retry_after(headers: Mapping[str, str], name: str | None, now: datetime) -> float | None:
    if not name or name not in headers:
        return None
    raw = headers[name].strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        try:
            when = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        return max(0.0, (when - now).total_seconds())


def _path_template(url: str) -> str:
    """A loggable path: digits and hex ids collapsed so logs group by endpoint."""
    path = urlsplit(url).path
    parts = []
    for seg in path.split("/"):
        if seg.isdigit() or (len(seg) >= 20 and all(c in "0123456789abcdef-" for c in seg.lower())):
            parts.append("{id}")
        else:
            parts.append(seg)
    return "/".join(parts)


# ---------------------------------------------------------------- client


class HttpClient:
    def __init__(
        self,
        *,
        base_url: str,
        transport: httpx2.AsyncBaseTransport,
        spec: HttpSpec,
        auth: AuthInjector | None = None,
        budget: RateBudget | None = None,
        capture: RawCapture | None = None,
        log: OpLog | None = None,
        clock: Clock = SYSTEM_CLOCK,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        scrub_fields: Iterable[str] = (),
        interactive: bool = False,
        stream: str | None = None,
        on_request: Callable[[], Awaitable[None]] | None = None,
        connector: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._connector = connector  # metric attribute (OPS-03)
        self._spec = spec
        self._auth = auth
        self._budget = budget or NullBudget()
        self._capture = capture
        self._log = log or MemoryOpLog()
        self._clock = clock
        self._sleep = sleep
        self._scrub = frozenset(scrub_fields)
        self._interactive = interactive
        self._stream = stream
        self._on_request = on_request
        self.vendor_requests = 0
        self._client = httpx2.AsyncClient(
            transport=transport,
            follow_redirects=True,
            max_redirects=3,
            timeout=httpx2.Timeout(spec.timeout_read_s, connect=spec.timeout_connect_s),
            headers=spec.default_headers,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def for_stream(self, stream: str | None) -> "HttpClient":
        """The same client, attributing errors and logs to ``stream``."""
        self._stream = stream
        return self

    def _observe(self, status: int | None, duration_ms: int) -> None:
        m = instruments()
        attrs = {"connector": self._connector, "status_class": status_class(status)}
        m.vendor_requests.add(1, attrs)
        m.vendor_request_duration.record(duration_ms / 1000, attrs)

    @property
    def clock(self) -> Clock:
        """The platform clock (tests freeze it): token expiry is measured against it."""
        return self._clock

    def url(self, path_or_url: str) -> str:
        if path_or_url.startswith(("http://", "https://")):
            return path_or_url
        return f"{self.base_url}/{path_or_url.lstrip('/')}"

    async def get_json(self, path: str, **kwargs: Any) -> Any:
        resp = await self.request("GET", path, **kwargs)
        return resp.json() if resp.content else None

    async def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        auth_scheme: str | None = "default",
        allow: Iterable[int] = (),
        cost: int | None = None,
        capture: bool = True,
    ) -> httpx2.Response:
        url = self.url(path_or_url)
        allowed = frozenset(allow)
        retry = self._spec.retry
        cost = (
            cost
            if cost is not None
            else (1 if method.upper() in ("GET", "HEAD") else self._spec.budget.write_cost)
        )
        refreshed = False
        transient_attempt = 0
        rate_sleeps = 0
        template = _path_template(url)

        while True:
            if self._on_request is not None:
                await self._on_request()
            await self._budget.acquire(cost, interactive=self._interactive)
            req_headers = dict(headers or {})
            material: AuthMaterial | None = None
            if self._auth is not None and auth_scheme is not None:
                material = await self._auth.material(auth_scheme, force_refresh=False)
                req_headers.update(material.headers)
            started = time.perf_counter()
            self.vendor_requests += 1
            try:
                resp = await self._client.request(
                    method, url, params=params, json=json_body, data=data, headers=req_headers
                )
            except (
                httpx2.TimeoutException,
                httpx2.NetworkError,
                httpx2.RemoteProtocolError,
            ) as exc:
                duration = int((time.perf_counter() - started) * 1000)
                self._observe(None, duration)
                self._log.http(
                    {
                        "method": method,
                        "path": template,
                        "status": None,
                        "duration_ms": duration,
                        "retry": transient_attempt,
                        "error": type(exc).__name__,
                    }
                )
                transient_attempt += 1
                if transient_attempt > retry.max_in_request_retries:
                    raise VendorUnavailable(f"{type(exc).__name__} calling {template}") from exc
                await self._sleep(self._backoff(transient_attempt))
                continue

            duration = int((time.perf_counter() - started) * 1000)
            self._observe(resp.status_code, duration)
            now = self._clock.now()
            remaining = _header_int(resp.headers, retry.remaining_header)
            limit = _header_int(resp.headers, retry.limit_header)
            reset_epoch = _header_int(resp.headers, retry.reset_header)
            reset_at = datetime.fromtimestamp(reset_epoch, UTC) if reset_epoch else None
            await self._budget.observe(remaining=remaining, limit=limit, reset_at=reset_at)
            self._log.http(
                {
                    "method": method,
                    "path": template,
                    "status": resp.status_code,
                    "duration_ms": duration,
                    "retry": transient_attempt + rate_sleeps,
                    "rate_remaining": remaining,
                }
            )

            status = resp.status_code
            if status in allowed:
                return resp
            if 200 <= status < 300 or status == 304:
                if capture and self._capture is not None and resp.content:
                    await self._capture.capture(
                        request_summary={
                            "method": method,
                            "path": template,
                            "query": dict(params or {}),
                            "status": status,
                        },
                        body=scrub_body(resp.content, self._scrub),
                    )
                return resp

            body_text = resp.text[:2000] if resp.content else ""
            # --- rate limiting: 403/429 with any rate signal (RATE-01)
            wait = self._rate_wait(resp, body_text, now, remaining, reset_at)
            if wait is not None:
                if wait > PARK_THRESHOLD_S or rate_sleeps >= _MAX_RATE_SLEEPS:
                    raise RateLimited(now + timedelta(seconds=wait))
                rate_sleeps += 1
                await self._sleep(wait)
                continue

            pattern = self._match_pattern(status, body_text)
            if pattern == "feature_not_enabled":
                raise FeatureNotEnabled(self._stream, template, message=body_text[:300])
            if pattern == "permission_missing":
                raise PermissionMissing(
                    self._stream, f"{method} {template}", message=body_text[:300]
                )

            # --- 401: one retry, only if a forced refresh yields a different token (RATE-05)
            if status == 401:
                if (
                    self._auth is not None
                    and auth_scheme is not None
                    and not refreshed
                    and material is not None
                ):
                    refreshed = True
                    fresh = await self._auth.material(auth_scheme, force_refresh=True)
                    if fresh.fingerprint and fresh.fingerprint != material.fingerprint:
                        continue
                raise AuthRejected(
                    f"vendor rejected the credential on {method} {template}",
                    endpoint=f"{method} {template}",
                )

            if retry.is_retryable_status(status):
                transient_attempt += 1
                if transient_attempt > retry.max_in_request_retries:
                    if status == 429:
                        raise RateLimited(now + timedelta(seconds=60))
                    raise VendorUnavailable(f"{status} from {method} {template}", status=status)
                await self._sleep(self._backoff(transient_attempt))
                continue

            raise VendorRejected(status, body=body_text, endpoint=f"{method} {template}")

    # ------------------------------------------------------------ internals

    def _backoff(self, attempt: int) -> float:
        base = min(30.0, 2.0 ** (attempt - 1))
        return base * random.uniform(0.8, 1.2)  # noqa: S311 - jitter, not crypto

    def _match_pattern(self, status: int, body: str) -> str | None:
        lowered = body.lower()
        for p in self._spec.retry.body_patterns:
            if p.status == status and p.contains.lower() in lowered:
                return p.treat_as
        return None

    def _rate_wait(
        self,
        resp: httpx2.Response,
        body: str,
        now: datetime,
        remaining: int | None,
        reset_at: datetime | None,
    ) -> float | None:
        if resp.status_code not in (403, 429):
            return None
        retry = self._spec.retry
        signals: list[float] = []
        after = _retry_after(resp.headers, retry.retry_after_header, now)
        if after is not None:
            signals.append(after)
        if remaining == 0 and reset_at is not None:
            signals.append(max(1.0, (reset_at - now).total_seconds()))
        if self._match_pattern(resp.status_code, body) == "rate_limited":
            signals.append(60.0)
        if not signals:
            return (
                60.0
                if resp.status_code == 429 and retry.is_retryable_status(429) is False
                else None
            )
        # The wait is the longest of the signals (part 6, section 7).
        return max(signals)
