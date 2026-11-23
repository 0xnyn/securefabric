"""OAuth2 for connectors: authorization code with PKCE, refresh, client credentials.

The platform drives these from the manifest's ``auth.oauth2`` block, so a connector
whose vendor speaks standard OAuth2 writes no auth code at all:

- ``OAUTH2``: the connect flow sends the user to ``authorize_url`` with a PKCE S256
  challenge; a control worker exchanges the code (``exchange_code``) and keeps only
  the refresh token (sealed). Access tokens are minted by ``refresh_exchange``
  under the shared refresh discipline (single flight, failure policy). With
  ``single_use_refresh_tokens`` the rotated refresh token is persisted with the
  access token in one transaction, so a crash cannot strand the only valid one.
- ``OAUTH2_CC``: ``client_credentials_exchange`` mints and caches tokens.

Token endpoint errors map onto the error taxonomy: ``invalid_grant`` and
``invalid_client`` are ``AuthRejected`` (counted by the failure policy), anything
else a vendor error.
"""

import base64
import hashlib
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from securefabric_cdk.errors import AuthRejected, VendorRejected, VendorUnavailable
from securefabric_cdk.tokens import CachedToken

Exchange = Callable[[CachedToken | None], Awaitable[CachedToken]]

# Without expires_in, assume an hour (RFC 6749 leaves it optional).
DEFAULT_LIFETIME = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class Pkce:
    verifier: str
    challenge: str
    method: str = "S256"


def pkce_pair() -> Pkce:
    """RFC 7636: a 43-character verifier (256 bits) and its S256 challenge."""
    verifier = secrets.token_urlsafe(32)
    return Pkce(verifier, s256(verifier))


def s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def authorize_url(
    endpoint: str,
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    scopes: list[str],
    pkce: Pkce | None,
    extra: dict[str, str] | None = None,
) -> str:
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        **({"scope": " ".join(scopes)} if scopes else {}),
        **(
            {"code_challenge": pkce.challenge, "code_challenge_method": pkce.method} if pkce else {}
        ),
        **(extra or {}),
    }
    sep = "&" if "?" in endpoint else "?"
    return f"{endpoint}{sep}{urlencode(query)}"


def _client_auth(client_id: str, client_secret: str | None) -> dict[str, str]:
    if not client_secret:
        return {}  # a public client sends client_id in the body
    raw = f"{client_id}:{client_secret}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


def parse_token_response(
    body: dict[str, Any], *, now: datetime, previous_refresh: str | None = None
) -> CachedToken:
    access = body.get("access_token")
    if not access:
        raise VendorUnavailable("the token endpoint returned no access_token")
    expires_in = body.get("expires_in")
    lifetime = timedelta(seconds=int(expires_in)) if expires_in else DEFAULT_LIFETIME
    new_refresh = body.get("refresh_token")
    return CachedToken(
        access_token=str(access),
        expires_at=now + lifetime,
        refresh_token=str(new_refresh) if new_refresh else previous_refresh,
        extra={
            "scope": body.get("scope"),
            # The store persists a rotated refresh token as the new credential.
            "rotated_refresh": bool(new_refresh) and new_refresh != previous_refresh,
        },
    )


async def _token_call(
    http: Any, token_url: str, form: dict[str, str], headers: dict[str, str]
) -> dict[str, Any]:
    resp = await http.request(
        "POST",
        token_url,
        data=form,
        headers={"Accept": "application/json", **headers},
        auth_scheme=None,
        allow=(400, 401),
        capture=False,  # token responses are never archived
    )
    body = resp.json() if resp.content else {}
    if resp.status_code in (400, 401):
        error = str(body.get("error") or resp.status_code)
        if error in ("invalid_grant", "invalid_client", "unauthorized_client") or (
            resp.status_code == 401
        ):
            raise AuthRejected(f"the token endpoint refused: {error}")
        raise VendorRejected(resp.status_code, f"the token endpoint refused: {error}")
    if not isinstance(body, dict):
        raise VendorUnavailable("the token endpoint returned no JSON object")
    return body


async def exchange_code(
    http: Any,
    token_url: str,
    *,
    client_id: str,
    client_secret: str | None,
    code: str,
    redirect_uri: str,
    code_verifier: str | None,
    now: datetime | None = None,
) -> CachedToken:
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        **({"code_verifier": code_verifier} if code_verifier else {}),
        **({} if client_secret else {"client_id": client_id}),
    }
    body = await _token_call(http, token_url, form, _client_auth(client_id, client_secret))
    return parse_token_response(body, now=now or datetime.now(UTC))


def refresh_exchange(
    http: Any,
    token_url: str,
    *,
    client_id: str,
    client_secret: str | None,
    refresh_token: str | None,
    scopes: list[str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Exchange:
    """An exchange for the shared refresh discipline: refresh with the newest refresh
    token (the cached one if it rotated, else the sealed credential)."""

    async def exchange(current: CachedToken | None) -> CachedToken:
        token = (current.refresh_token if current else None) or refresh_token
        if not token:
            raise AuthRejected("no refresh token: authorise the connection again")
        form = {
            "grant_type": "refresh_token",
            "refresh_token": token,
            **({"scope": " ".join(scopes)} if scopes else {}),
            **({} if client_secret else {"client_id": client_id}),
        }
        body = await _token_call(http, token_url, form, _client_auth(client_id, client_secret))
        now = clock() if clock else datetime.now(UTC)
        return parse_token_response(body, now=now, previous_refresh=token)

    return exchange


def client_credentials_exchange(
    http: Any,
    token_url: str,
    *,
    client_id: str,
    client_secret: str,
    scopes: list[str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Exchange:
    async def exchange(_current: CachedToken | None) -> CachedToken:
        form = {
            "grant_type": "client_credentials",
            **({"scope": " ".join(scopes)} if scopes else {}),
        }
        body = await _token_call(http, token_url, form, _client_auth(client_id, client_secret))
        now = clock() if clock else datetime.now(UTC)
        token = parse_token_response(body, now=now)
        token.refresh_token = None  # client credentials never refresh; they re-mint
        token.extra["rotated_refresh"] = False
        return token

    return exchange
