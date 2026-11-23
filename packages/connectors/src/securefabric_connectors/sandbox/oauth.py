"""The SANDBOX vendor's OAuth2 server (docs/plan/05-connector-sdk.md, section 6).

It exists to exercise what GitHub does not: authorization code with PKCE (S256
required), single-use rotating refresh tokens with reuse detection, and client
credentials. Codes and tokens are HMAC-signed and self-validating, so any process
can check them; the "vendor database" (spent codes, the newest refresh token of
each family) lives in process memory, like the rest of the SANDBOX vendor.

Clients: any ``client_id`` starting ``sbxc_`` is registered; its secret is
``client_secret_for(client_id)``. ``sbxc_revoked*`` clients are refused.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode

from securefabric_cdk.inprocess import VendorRequest, VendorResponse

# The simulated vendor's own signing secret (not a platform secret).
_ISSUER_KEY = b"securefabric-sandbox-oauth-issuer-v1"
CODE_TTL_S = 600
DEFAULT_ACCESS_TTL_S = 3600

_spent_codes: set[str] = set()
_families: dict[str, int] = {}  # refresh family -> newest generation
_revoked_families: set[str] = set()


def reset_oauth() -> None:
    _spent_codes.clear()
    _families.clear()
    _revoked_families.clear()


def client_secret_for(client_id: str) -> str:
    mac = hmac.new(_ISSUER_KEY, b"client:" + client_id.encode(), hashlib.sha256).hexdigest()
    return "sbxcs_" + mac[:32]


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(prefix: str, payload: dict[str, Any]) -> str:
    body = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    mac = _b64(hmac.new(_ISSUER_KEY, (prefix + body).encode(), hashlib.sha256).digest())
    return f"{prefix}{body}.{mac}"


def _verify(token: str, prefix: str) -> dict[str, Any] | None:
    if not token.startswith(prefix) or "." not in token:
        return None
    body, mac = token[len(prefix) :].rsplit(".", 1)
    good = _b64(hmac.new(_ISSUER_KEY, (prefix + body).encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(mac, good):
        return None
    try:
        payload: dict[str, Any] = json.loads(_unb64(body))
    except ValueError:
        return None
    return payload


def access_token_tenant(token: str) -> str | None:
    """The tenant an access token is for, or None if it is forged or expired."""
    p = _verify(token, "sbxat_")
    if p is None or p.get("exp", 0) < time.time():
        return None
    return str(p["tenant"])


def _s256(verifier: str) -> str:
    return _b64(hashlib.sha256(verifier.encode("ascii")).digest())


def _err(status: int, error: str, description: str = "") -> VendorResponse:
    return VendorResponse(status, {"error": error, "error_description": description})


def _client(request: VendorRequest, form: dict[str, str]) -> str | None:
    """Authenticate the client (HTTP Basic or form fields). Returns its id."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        try:
            cid, _, secret = base64.b64decode(auth[6:]).decode().partition(":")
        except ValueError:
            return None
    else:
        cid, secret = form.get("client_id", ""), form.get("client_secret", "")
    if not cid.startswith("sbxc_") or cid.startswith("sbxc_revoked"):
        return None
    if not hmac.compare_digest(secret, client_secret_for(cid)):
        return None
    return cid


class OAuthServer:
    def __init__(self, options: dict[str, Any]) -> None:
        self._access_ttl = int(options.get("token_ttl", DEFAULT_ACCESS_TTL_S))

    def handle(self, route: str, request: VendorRequest) -> VendorResponse | None:
        if route == "/oauth/authorize" and request.method == "GET":
            return self._authorize(request.query)
        if route == "/oauth/token" and request.method == "POST":
            return self._token(request)
        return None

    # ------------------------------------------------------------ authorize

    def _authorize(self, q: dict[str, str]) -> VendorResponse:
        redirect_uri, state = q.get("redirect_uri", ""), q.get("state", "")
        cid = q.get("client_id", "")
        if not redirect_uri.startswith(("https://", "http://")) or not cid.startswith("sbxc_"):
            return _err(400, "invalid_request", "unknown client or redirect_uri")

        def back(params: dict[str, str]) -> VendorResponse:
            sep = "&" if "?" in redirect_uri else "?"
            location = f"{redirect_uri}{sep}{urlencode({**params, 'state': state})}"
            return VendorResponse(302, None, {"location": location})

        if q.get("deny"):
            return back({"error": "access_denied", "error_description": "the user declined"})
        if q.get("response_type") != "code":
            return back({"error": "unsupported_response_type"})
        if q.get("code_challenge_method") != "S256" or not q.get("code_challenge"):
            return back({"error": "invalid_request", "error_description": "PKCE S256 required"})
        tenant = q.get("tenant") or "t_oauth_" + hashlib.sha256(cid.encode()).hexdigest()[:8]
        code = _sign(
            "sbxcode_",
            {
                "cid": cid,
                "ru": redirect_uri,
                "cc": q["code_challenge"],
                "tenant": tenant,
                "scope": q.get("scope", "read"),
                "exp": time.time() + CODE_TTL_S,
                "n": secrets.token_hex(8),
            },
        )
        return back({"code": code})

    # ------------------------------------------------------------ token

    def _issue(
        self, cid: str, tenant: str, scope: str, family: str | None, gen: int
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "access_token": _sign(
                "sbxat_", {"tenant": tenant, "cid": cid, "exp": time.time() + self._access_ttl}
            ),
            "token_type": "Bearer",
            "expires_in": self._access_ttl,
            "scope": scope,
        }
        if family is not None:
            _families[family] = gen
            out["refresh_token"] = _sign(
                "sbxrt_",
                {"family": family, "gen": gen, "tenant": tenant, "cid": cid, "scope": scope},
            )
        return out

    def _token(self, request: VendorRequest) -> VendorResponse:
        form = dict(parse_qsl(request.body.decode() if request.body else ""))
        cid = _client(request, form)
        if cid is None:
            return _err(401, "invalid_client")
        grant = form.get("grant_type")
        if grant == "authorization_code":
            code = _verify(form.get("code", ""), "sbxcode_")
            if code is None or code["exp"] < time.time() or code["cid"] != cid:
                return _err(400, "invalid_grant", "unknown or expired code")
            if code["n"] in _spent_codes:
                return _err(400, "invalid_grant", "code already used")
            if code["ru"] != form.get("redirect_uri"):
                return _err(400, "invalid_grant", "redirect_uri mismatch")
            if _s256(form.get("code_verifier", "")) != code["cc"]:
                return _err(400, "invalid_grant", "PKCE verification failed")
            _spent_codes.add(code["n"])
            body = self._issue(cid, code["tenant"], code["scope"], secrets.token_hex(8), 1)
            return VendorResponse(200, body)
        if grant == "refresh_token":
            rt = _verify(form.get("refresh_token", ""), "sbxrt_")
            if rt is None or rt["cid"] != cid or rt["family"] in _revoked_families:
                return _err(400, "invalid_grant", "unknown or revoked refresh token")
            if rt["gen"] != _families.get(rt["family"]):
                # Reuse of a rotated token: assume theft and revoke the whole family.
                _revoked_families.add(rt["family"])
                return _err(400, "invalid_grant", "refresh token reused; family revoked")
            body = self._issue(cid, rt["tenant"], rt["scope"], rt["family"], rt["gen"] + 1)
            return VendorResponse(200, body)
        if grant == "client_credentials":
            tenant = "t_cc_" + hashlib.sha256(cid.encode()).hexdigest()[:8]
            return VendorResponse(200, self._issue(cid, tenant, form.get("scope", "read"), None, 0))
        return _err(400, "unsupported_grant_type")
