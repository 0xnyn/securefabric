"""Auth primitives connectors may use without importing a crypto library."""

import time
from typing import Any

import jwt


def sign_jwt_rs256(claims: dict[str, Any], private_key_pem: str) -> str:
    return jwt.encode(claims, private_key_pem, algorithm="RS256")


def github_app_jwt(
    app_id: str, private_key_pem: str, *, now: float | None = None
) -> tuple[str, float]:
    """A GitHub App JWT: issuer is the app id, 9-minute expiry, issued-at backdated
    60 seconds for clock drift (docs/plan/06-github-connector.md, section 4).
    Returns ``(token, expires_at_epoch)``."""
    t = int(now if now is not None else time.time())
    exp = t + 9 * 60
    return sign_jwt_rs256({"iat": t - 60, "exp": exp, "iss": str(app_id)}, private_key_pem), float(
        exp
    )
