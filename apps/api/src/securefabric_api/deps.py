"""FastAPI dependencies: the platform, the principal, idempotency, strict params.

Both authenticators produce the same :class:`Principal`; nothing below this
layer knows which was used (part 3, section 4).
"""

import hashlib
import json
from collections.abc import Callable, Iterable
from typing import Annotated, Any

from fastapi import Depends, Request
from psycopg import errors as pg_errors

from securefabric_api.errors import IdempotentReplay
from securefabric_api.ratelimit import RateLimiter, retry_after
from securefabric_core import (
    BadRequestError,
    ConflictError,
    RateLimitedError,
    UnauthenticatedError,
    ValidationFailedError,
)
from securefabric_core.telemetry import instruments
from securefabric_db import fetch_one, tenant_tx
from securefabric_domain.connect import authenticate_session_token
from securefabric_domain.runtime import Platform
from securefabric_domain.tenancy import Principal, authenticate_api_key
from securefabric_domain.workos import WorkOSClient, authenticate_session


def get_platform(request: Request) -> Platform:
    platform: Platform = request.app.state.platform
    return platform


PlatformDep = Annotated[Platform, Depends(get_platform)]


def bearer_token(request: Request) -> str | None:
    if key := request.headers.get("x-api-key"):
        return key.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _apply_rate_limit(request: Request, principal: Principal) -> None:
    limiter: RateLimiter | None = getattr(request.app.state, "rate_limiter", None)
    if limiter is None or principal.environment_id is None:
        return
    decision = limiter.check(principal.environment_id)
    request.state.rate = decision
    if not decision.allowed:
        instruments().api_rate_limited.add(1)
        raise RateLimitedError(
            "Rate limit exceeded for this environment.",
            code="rate_limited",
            headers={
                "Retry-After": str(retry_after(decision)),
                "X-RateLimit-Limit": str(decision.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(decision.reset),
            },
        )


async def get_principal(request: Request, platform: PlatformDep) -> Principal:
    token = bearer_token(request)
    if not token:
        raise UnauthenticatedError(
            "Send an API key (Authorization: Bearer sfk_… or X-API-KEY) or a session token.",
            code="unauthenticated",
        )
    if token.startswith("sfk_"):
        principal = await authenticate_api_key(platform, token)
        env_header = request.headers.get("x-environment-id")
        if env_header and env_header not in (str(principal.environment_id),):
            # A key is bound to one environment; a mismatched header is a 404 by the TEN-02 rule.
            from securefabric_core import NotFoundError

            raise NotFoundError("Environment not found", code="environment_not_found")
    elif token.startswith("sfcs_"):
        raise UnauthenticatedError(
            "Connect session tokens are only valid on /v1/connect endpoints.",
            code="invalid_credential_for_route",
        )
    else:
        workos: WorkOSClient | None = getattr(request.app.state, "workos", None)
        if workos is None:
            raise UnauthenticatedError(
                "Session authentication is not configured.", code="sessions_disabled"
            )
        principal = await authenticate_session(
            platform, workos, token, request.headers.get("x-environment-id")
        )
    principal = principal.with_request(
        request_id=getattr(request.state, "request_id", None),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _apply_rate_limit(request, principal)
    request.state.principal = principal
    return principal


PrincipalDep = Annotated[Principal, Depends(get_principal)]


async def get_connect_principal(request: Request, platform: PlatformDep) -> Principal:
    token = bearer_token(request) or request.cookies.get("sf_connect")
    if not token:
        raise UnauthenticatedError("Missing connect session token.", code="unauthenticated")
    principal = await authenticate_session_token(platform, token)
    principal = principal.with_request(
        request_id=getattr(request.state, "request_id", None),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _apply_rate_limit(request, principal)
    return principal


ConnectPrincipalDep = Annotated[Principal, Depends(get_connect_principal)]


def require_session(principal: Principal) -> None:
    if principal.kind != "user":
        from securefabric_core import PermissionDeniedError

        raise PermissionDeniedError(
            "This endpoint is only available to dashboard sessions.", code="session_required"
        )


# ---------------------------------------------------------------- strict query params (API-05)


def allow_params(*allowed: str) -> Callable[[Request], None]:
    allowed_set = frozenset(allowed) | {"cursor", "limit"}

    def check(request: Request) -> None:
        unknown = [
            k for k in request.query_params if k not in allowed_set and not k.startswith("tags[")
        ]
        if unknown:
            raise BadRequestError(
                f"Unknown query parameter {unknown[0]!r}.",
                code="unknown_parameter",
                errors=[{"field": k, "message": "unknown parameter"} for k in unknown],
            )

    return check


def csv(value: str | None) -> list[str] | None:
    if value is None or value == "":
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


def parse_bool(name: str, value: str | None) -> bool | None:
    """Tri-state filters accept true or false; null is a 422, as in Leen."""
    if value is None:
        return None
    lowered = value.lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    raise ValidationFailedError(
        f"{name} must be true or false.",
        code="invalid_filter",
        errors=[{"field": name, "message": "must be true or false"}],
    )


def tag_filters(request: Request) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in request.query_params.items():
        if k.startswith("tags[") and k.endswith("]"):
            out[k[5:-1]] = v
    return out


# ---------------------------------------------------------------- idempotency (API-08)


async def idempotency(request: Request, principal: PrincipalDep, platform: PlatformDep) -> None:
    """``Idempotency-Key`` on a POST: the first response is stored and a replay
    within 24 hours returns it with ``Idempotent-Replayed: true``. A replay with a
    different body is a 422."""
    key = request.headers.get("idempotency-key")
    if not key or request.method != "POST" or principal.environment_id is None:
        return
    if len(key) > 255:
        raise BadRequestError("Idempotency-Key is too long.", code="invalid_idempotency_key")
    body = await request.body()
    digest = hashlib.sha256(
        request.method.encode() + request.url.path.encode() + b"\n" + body
    ).digest()
    env = principal.environment_id
    async with tenant_tx(platform.pool, env) as conn:
        row = await fetch_one(
            conn,
            "select * from control.idempotency_key where environment_id = %s and key = %s "
            "and created_at > now() - interval '24 hours'",
            (env, key),
        )
        if row is not None:
            if bytes(row["request_hash"]) != digest:
                raise ValidationFailedError(
                    "This Idempotency-Key was used with a different request.",
                    code="idempotency_key_reused",
                )
            if row["status"] is None:
                raise ConflictError(
                    "A request with this Idempotency-Key is in progress.",
                    code="idempotency_in_progress",
                )
            raise IdempotentReplay(row["status"], row["response"])
        await conn.execute(
            "delete from control.idempotency_key where environment_id = %s and key = %s", (env, key)
        )
        try:
            await conn.execute(
                "insert into control.idempotency_key (environment_id, key, request_hash) values (%s, %s, %s)",
                (env, key, digest),
            )
        except pg_errors.UniqueViolation as exc:
            raise ConflictError(
                "A request with this Idempotency-Key is in progress.",
                code="idempotency_in_progress",
            ) from exc
    request.state.idempotency = (env, key)


async def store_idempotent_response(
    platform: Platform, env: Any, key: str, status: int, body: bytes
) -> None:
    async with tenant_tx(platform.pool, env) as conn:
        if status >= 500:
            await conn.execute(
                "delete from control.idempotency_key where environment_id = %s and key = %s",
                (env, key),
            )
            return
        try:
            parsed = json.loads(body) if body else None
        except ValueError:
            parsed = None
        await conn.execute(
            "update control.idempotency_key set status = %s, response = %s where environment_id = %s and key = %s",
            (status, json.dumps(parsed), env, key),
        )


IdempotencyDep = Depends(idempotency)


def uuids(values: Iterable[str] | None, field: str) -> list[Any] | None:
    from uuid import UUID

    if values is None:
        return None
    out = []
    for v in values:
        try:
            out.append(UUID(v))
        except ValueError:
            raise ValidationFailedError(
                f"{field} must contain UUIDs.",
                code="invalid_filter",
                errors=[{"field": field, "message": f"{v!r} is not a UUID"}],
            ) from None
    return out
