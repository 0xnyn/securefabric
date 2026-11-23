"""Recorded vendor responses: replay, record and scrub (CDK-04, CDK-05).

A fixture file is JSON::

    {"interactions": [
        {"request":  {"method": "GET", "path": "/orgs/acme/dependabot/alerts",
                      "query": {"per_page": "100"}},
         "response": {"status": 200, "headers": {"link": "..."}, "body": [...]}},
        ...
    ]}

Hosts are ignored when matching, so ``Link`` URLs that point at the vendor's
absolute host replay fine. Identical requests replay their response again.

Recording scrubs authorization headers, cookies, anything matching a secret
pattern, and connector-declared sensitive fields (GitHub's ``secret``).
"""

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import httpx2

from securefabric_cdk.http import scrub_json
from securefabric_core.redact import REDACTED, redact

_KEEP_HEADERS = frozenset(
    {
        "link",
        "content-type",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "x-ratelimit-used",
        "x-ratelimit-resource",
        "retry-after",
        "etag",
        "x-total-count",
    }
)


def _query(url: httpx2.URL | str) -> dict[str, str]:
    raw = urlsplit(url).query if isinstance(url, str) else url.query.decode()
    return dict(sorted(parse_qsl(raw, keep_blank_values=True)))


def _key(method: str, path: str, query: dict[str, str]) -> str:
    return (
        f"{method.upper()} {path} {json.dumps(dict(sorted(query.items())), separators=(',', ':'))}"
    )


@dataclass
class Interaction:
    method: str
    path: str
    query: dict[str, str]
    status: int
    headers: dict[str, str]
    body: Any

    @property
    def key(self) -> str:
        return _key(self.method, self.path, self.query)

    def to_json(self) -> dict[str, Any]:
        return {
            "request": {"method": self.method, "path": self.path, "query": self.query},
            "response": {"status": self.status, "headers": self.headers, "body": self.body},
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Interaction":
        req, resp = data["request"], data["response"]
        return cls(
            method=req["method"].upper(),
            path=req["path"],
            query={k: str(v) for k, v in (req.get("query") or {}).items()},
            status=int(resp.get("status", 200)),
            headers={k.lower(): str(v) for k, v in (resp.get("headers") or {}).items()},
            body=resp.get("body"),
        )


def load_fixture(path: Path) -> list[Interaction]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Interaction.from_json(i) for i in data["interactions"]]


def load_fixtures(paths: Iterable[Path]) -> list[Interaction]:
    out: list[Interaction] = []
    for p in paths:
        out.extend(load_fixture(p))
    return out


def save_fixture(path: Path, interactions: Iterable[Interaction]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"interactions": [i.to_json() for i in interactions]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


# An injector sees each request (and its 0-based ordinal) and may return a
# response to send instead of the fixture's. Used for failure scenarios.
type Injector = Callable[[httpx2.Request, int], httpx2.Response | None]


@dataclass
class ReplayTransport(httpx2.AsyncBaseTransport):
    interactions: list[Interaction]
    injectors: list[Injector] = field(default_factory=list)
    strict: bool = True
    requests: list[httpx2.Request] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_key: dict[str, Interaction] = {}
        for i in self.interactions:
            self._by_key[i.key] = i

    def remove(self, predicate: Callable[[Interaction], bool]) -> None:
        self.interactions = [i for i in self.interactions if not predicate(i)]
        self.__post_init__()

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        ordinal = len(self.requests)
        self.requests.append(request)
        for inject in self.injectors:
            injected = inject(request, ordinal)
            if injected is not None:
                return injected
        key = _key(request.method, request.url.path, _query(request.url))
        hit = self._by_key.get(key)
        if hit is None:
            if self.strict:
                known = "\n  ".join(sorted(self._by_key)[:20])
                raise AssertionError(f"no fixture for {key}\nknown:\n  {known}")
            return httpx2.Response(404, json={"message": "Not Found"}, request=request)
        content = b"" if hit.body is None else json.dumps(hit.body).encode()
        headers = dict(hit.headers)
        if hit.body is not None:
            headers.setdefault("content-type", "application/json")
        return httpx2.Response(hit.status, headers=headers, content=content, request=request)


def fail_on(
    status: int,
    *,
    ordinal: int | None = None,
    path_contains: str | None = None,
    every: int | None = None,
    headers: dict[str, str] | None = None,
    body: Any = None,
    times: int | None = None,
) -> Injector:
    """Build an injector that answers matching requests with ``status``."""
    fired = {"n": 0}

    def inject(request: httpx2.Request, n: int) -> httpx2.Response | None:
        if times is not None and fired["n"] >= times:
            return None
        if ordinal is not None and n != ordinal:
            return None
        if every is not None and (n + 1) % every != 0:
            return None
        if path_contains is not None and path_contains not in request.url.path:
            return None
        fired["n"] += 1
        return httpx2.Response(
            status,
            headers=headers or {},
            json=body if body is not None else {"message": f"injected {status}"},
            request=request,
        )

    return inject


class RecordingTransport(httpx2.AsyncBaseTransport):
    """Wraps a real transport and keeps scrubbed copies of every exchange."""

    def __init__(
        self, inner: httpx2.AsyncBaseTransport, *, scrub_fields: Iterable[str] = ()
    ) -> None:
        self._inner = inner
        self._scrub = frozenset(scrub_fields)
        self.interactions: list[Interaction] = []

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        response = await self._inner.handle_async_request(request)
        body_bytes = await response.aread()
        try:
            body: Any = json.loads(body_bytes) if body_bytes else None
        except ValueError:
            body = body_bytes.decode("utf-8", "replace")
        self.interactions.append(
            Interaction(
                method=request.method,
                path=request.url.path,
                query=_query(request.url),
                status=response.status_code,
                headers={
                    k.lower(): v for k, v in response.headers.items() if k.lower() in _KEEP_HEADERS
                },
                body=scrub_fixture_body(body, self._scrub),
            )
        )
        # aread() already decoded the body: pass it on without the transfer encoding headers,
        # or the client decompresses the plain bytes a second time (real vendors gzip).
        headers = [
            (k, v)
            for k, v in response.headers.multi_items()
            if k.lower() not in ("content-encoding", "content-length", "transfer-encoding")
        ]
        return httpx2.Response(
            response.status_code, headers=headers, content=body_bytes, request=request
        )

    async def aclose(self) -> None:
        await self._inner.aclose()


def scrub_fixture_body(body: Any, fields: frozenset[str]) -> Any:
    return redact(scrub_json(body, fields))


def find_secrets(value: Any, fields: Iterable[str] = ("secret",)) -> list[str]:
    """Paths in ``value`` that hold a scrubbed field or an unredacted secret (CI scan)."""
    hits: list[str] = []
    names = frozenset(fields)

    def walk(v: Any, path: str) -> None:
        if isinstance(v, dict):
            for k, child in v.items():
                if k in names:
                    hits.append(f"{path}.{k}")
                walk(child, f"{path}.{k}")
        elif isinstance(v, list):
            for i, child in enumerate(v):
                walk(child, f"{path}[{i}]")
        elif isinstance(v, str) and v != REDACTED and redact(v) != v:
            hits.append(path)

    walk(value, "$")
    return hits
