"""Pure-ASGI request middleware (cheaper than BaseHTTPMiddleware).

- Assigns or propagates ``X-Request-Id`` (``req_…``) and binds it to logs.
- Adds ``X-RateLimit-*`` headers once the principal dependency has decided.
- Stores the response of an ``Idempotency-Key`` POST for replay (API-08).
- Emits one access log line per request. Bodies are never logged (SEC-07).
"""

import time
import uuid
from typing import Any

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from securefabric_core import get_logger
from securefabric_core.telemetry import instruments, status_class

REQUEST_ID_HEADER = "x-request-id"

log = get_logger("securefabric_api.access")


def route_template(scope: Scope) -> str:
    """The matched route as a template (``/v1/connections/{connection_id}``): the
    request path with each path-parameter segment named, so metrics never carry ids."""
    if scope.get("route") is None:
        return "unmatched"
    values = {str(v): k for k, v in (scope.get("path_params") or {}).items()}
    return "/".join(
        f"{{{values[seg]}}}" if seg in values else seg for seg in scope["path"].split("/")
    )


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(REQUEST_ID_HEADER.encode())
        request_id = incoming.decode("latin-1")[:128] if incoming else f"req_{uuid.uuid4().hex}"
        state: dict[str, Any] = scope.setdefault("state", {})
        state["request_id"] = request_id
        status_code = 500
        start = time.perf_counter()
        captured: list[bytes] = []
        capture = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, capture
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                rate = state.get("rate")
                if rate is not None:
                    headers["x-ratelimit-limit"] = str(rate.limit)
                    headers["x-ratelimit-remaining"] = str(rate.remaining)
                    headers["x-ratelimit-reset"] = str(rate.reset)
                capture = "idempotency" in state and "idempotent-replayed" not in headers
            elif message["type"] == "http.response.body" and capture:
                captured.append(message.get("body", b""))
            await send(message)

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            try:
                await self.app(scope, receive, send_wrapper)
            finally:
                if capture and "idempotency" in state:
                    from securefabric_api.deps import store_idempotent_response

                    env, key = state["idempotency"]
                    app = scope["app"]
                    try:
                        await store_idempotent_response(
                            app.state.platform, env, key, status_code, b"".join(captured)
                        )
                    except Exception as exc:  # never fail the request over bookkeeping
                        log.warning("idempotency_store_failed", error=type(exc).__name__)
                elapsed = time.perf_counter() - start
                if scope["path"] not in {"/health/live", "/health/ready"}:
                    route = route_template(scope)
                    instruments().api_request_duration.record(
                        elapsed,
                        {
                            "route": route,
                            "method": scope["method"],
                            "status_class": status_class(status_code),
                        },
                    )
                    log.info(
                        "request",
                        method=scope["method"],
                        path=scope["path"],
                        status=status_code,
                        duration_ms=round(elapsed * 1000, 2),
                    )
