"""In-process vendors (SANDBOX) behind the real HTTP client, with no network.

A connector supplies a plain handler ``VendorRequest -> VendorResponse``; the
CDK wraps it in a transport so requests still pass through the full client
(auth, retries, budget, capture, logging). Connector code never imports an
HTTP library (CDK-03).
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl

import httpx2


@dataclass(frozen=True, slots=True)
class VendorRequest:
    method: str
    url: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body) if self.body else None


@dataclass(frozen=True, slots=True)
class VendorResponse:
    status: int
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)


type VendorHandler = Callable[[VendorRequest], VendorResponse]


class InProcessTransport(httpx2.AsyncBaseTransport):
    def __init__(self, handler: VendorHandler) -> None:
        self._handler = handler

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        body = await request.aread()
        vreq = VendorRequest(
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            query=dict(parse_qsl(request.url.query.decode(), keep_blank_values=True)),
            headers={k.lower(): v for k, v in request.headers.items()},
            body=body,
        )
        vresp = self._handler(vreq)
        content = b"" if vresp.body is None else json.dumps(vresp.body).encode()
        headers = {"content-type": "application/json", **vresp.headers}
        return httpx2.Response(vresp.status, headers=headers, content=content, request=request)
