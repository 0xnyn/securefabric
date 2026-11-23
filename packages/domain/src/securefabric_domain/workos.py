"""WorkOS AuthKit for dashboard users (docs/plan/03-tenancy-connections-vault.md, section 2).

Access tokens are RS256 JWTs verified against WorkOS's JWKS (cached). The user
and organization in the claims map to ``app_user`` and ``account``, created on
first sight (just-in-time provisioning). See docs/research/leen-v2-and-workos.md.
"""

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx2
import jwt

from securefabric_core import UnauthenticatedError, UnavailableError, get_logger
from securefabric_db import fetch_all, fetch_one
from securefabric_domain.runtime import Platform
from securefabric_domain.tenancy import (
    ROLE_SCOPES,
    Principal,
    provision_account,
    resolve_environment,
    upsert_user,
)

log = get_logger(__name__)

JWKS_TTL_S = 600.0


class WorkOSClient:
    def __init__(
        self,
        *,
        client_id: str,
        api_key: str,
        api_url: str = "https://api.workos.com",
        transport: Callable[[], httpx2.AsyncBaseTransport] | None = None,
    ) -> None:
        self.client_id = client_id
        self._api_key = api_key
        self.api_url = api_url.rstrip("/")
        self._transport = transport
        self._jwks: dict[str, Any] | None = None
        self._jwks_at = 0.0
        self._lock = asyncio.Lock()
        self._users: dict[str, dict[str, Any]] = {}

    def _client(self) -> httpx2.AsyncClient:
        kwargs: dict[str, Any] = {"timeout": 10.0, "base_url": self.api_url}
        if self._transport is not None:
            kwargs["transport"] = self._transport()
        return httpx2.AsyncClient(**kwargs)

    async def _request(
        self, method: str, path: str, *, json_body: Any = None, auth: bool = True
    ) -> Any:
        headers = {"Authorization": f"Bearer {self._api_key}"} if auth else {}
        async with self._client() as c:
            try:
                resp = await c.request(method, path, json=json_body, headers=headers)
            except httpx2.HTTPError as exc:
                raise UnavailableError(
                    "WorkOS is unreachable", code="identity_unavailable"
                ) from exc
        if resp.status_code >= 500:
            raise UnavailableError("WorkOS returned an error", code="identity_unavailable")
        if resp.status_code >= 400:
            body = resp.json() if resp.content else {}
            raise UnauthenticatedError(
                body.get("message")
                or body.get("error_description")
                or "WorkOS rejected the request",
                code=str(body.get("code") or body.get("error") or "identity_rejected"),
            )
        return resp.json() if resp.content else None

    # ------------------------------------------------------------ tokens

    async def jwks(self, *, force: bool = False) -> dict[str, Any]:
        if not force and self._jwks and time.monotonic() - self._jwks_at < JWKS_TTL_S:
            return self._jwks
        async with self._lock:
            if force or not self._jwks or time.monotonic() - self._jwks_at >= JWKS_TTL_S:
                self._jwks = await self._request("GET", f"/sso/jwks/{self.client_id}", auth=False)
                self._jwks_at = time.monotonic()
        assert self._jwks is not None
        return self._jwks

    def accepted_issuers(self) -> set[str]:
        return {
            "https://api.workos.com",
            "https://api.workos.com/",
            f"https://api.workos.com/user_management/{self.client_id}",
            self.api_url,
        }

    async def verify_access_token(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise UnauthenticatedError(
                "The session token is malformed.", code="invalid_session"
            ) from exc
        if header.get("alg") != "RS256":
            raise UnauthenticatedError(
                "Unsupported session token algorithm.", code="invalid_session"
            )
        key = await self._key_for(header.get("kid"))
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                options={"verify_aud": False, "require": ["exp", "sub"]},
                leeway=30,
            )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthenticatedError("The session has expired.", code="session_expired") from exc
        except jwt.PyJWTError as exc:
            raise UnauthenticatedError(
                "The session token is invalid.", code="invalid_session"
            ) from exc
        if claims.get("iss") not in self.accepted_issuers():
            raise UnauthenticatedError(
                "The session token has an unexpected issuer.", code="invalid_session"
            )
        if claims.get("client_id") not in (None, self.client_id):
            raise UnauthenticatedError(
                "The session token is for another client.", code="invalid_session"
            )
        return claims

    async def _key_for(self, kid: str | None) -> Any:
        for force in (False, True):  # unknown kid: refetch once (key rotation)
            for jwk in (await self.jwks(force=force)).get("keys", []):
                if kid is None or jwk.get("kid") == kid:
                    return jwt.PyJWK(jwk).key
        raise UnauthenticatedError(
            "The session token's signing key is unknown.", code="invalid_session"
        )

    # ------------------------------------------------------------ REST

    async def get_user(self, user_id: str) -> dict[str, Any]:
        if user_id not in self._users:
            self._users[user_id] = await self._request("GET", f"/user_management/users/{user_id}")
        return self._users[user_id]

    async def get_organization(self, org_id: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._request("GET", f"/organizations/{org_id}")
        return result

    async def create_organization(self, name: str) -> dict[str, Any]:
        result: dict[str, Any] = await self._request(
            "POST", "/organizations", json_body={"name": name}
        )
        return result

    async def create_membership(
        self, *, user_id: str, organization_id: str, role_slug: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"user_id": user_id, "organization_id": organization_id}
        if role_slug:
            body["role_slug"] = role_slug
        result: dict[str, Any] = await self._request(
            "POST", "/user_management/organization_memberships", json_body=body
        )
        return result

    async def send_invitation(
        self, *, email: str, organization_id: str, inviter_user_id: str | None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"email": email, "organization_id": organization_id}
        if inviter_user_id:
            body["inviter_user_id"] = inviter_user_id
        result: dict[str, Any] = await self._request(
            "POST", "/user_management/invitations", json_body=body
        )
        return result

    async def revoke_invitation(self, invitation_id: str) -> None:
        await self._request("POST", f"/user_management/invitations/{invitation_id}/revoke")

    def authorization_url(self, *, redirect_uri: str, state: str | None = None) -> str:
        q = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "provider": "authkit",
        }
        if state:
            q["state"] = state
        return f"{self.api_url}/user_management/authorize?{urlencode(q)}"

    async def authenticate(self, **grant: Any) -> dict[str, Any]:
        """``grant_type`` authorization_code | refresh_token | password."""
        body = {"client_id": self.client_id, "client_secret": self._api_key, **grant}
        result: dict[str, Any] = await self._request(
            "POST", "/user_management/authenticate", json_body=body, auth=False
        )
        return result


def build_workos(platform: Platform) -> WorkOSClient | None:
    s = platform.settings
    if not s.workos_client_id or not s.workos_api_key:
        return None
    return WorkOSClient(
        client_id=s.workos_client_id,
        api_key=s.workos_api_key.get_secret_value(),
        api_url=s.workos_api_url,
    )


async def authenticate_session(
    platform: Platform, workos: WorkOSClient, token: str, environment_ref: str | None
) -> Principal:
    claims = await workos.verify_access_token(token)
    workos_user_id = str(claims["sub"])
    async with platform.pool.connection() as conn:
        user = await fetch_one(
            conn, "select * from control.app_user where workos_user_id = %s", (workos_user_id,)
        )
    if user is None:
        profile = await workos.get_user(workos_user_id)
        name = (
            " ".join(p for p in (profile.get("first_name"), profile.get("last_name")) if p) or None
        )
        async with platform.pool.connection() as conn, conn.transaction():
            user = await upsert_user(
                conn, workos_user_id=workos_user_id, email=profile["email"], name=name
            )
    account, role = await _account_for(platform, workos, user["id"], claims.get("org_id"))
    environment_id: UUID | None = None
    if account is not None and environment_ref:
        env = await resolve_environment(platform, account["id"], environment_ref)
        environment_id = env["id"]
    scopes = ROLE_SCOPES.get(role or "", frozenset())
    return Principal(
        kind="user",
        account_id=account["id"] if account else None,
        environment_id=environment_id,
        scopes=scopes,
        actor_id=str(user["id"]),
        role=role,
        is_operator=bool(user["is_operator"]),
        extra={
            "email": user["email"],
            "workos_user_id": workos_user_id,
            "workos_org_id": claims.get("org_id"),
            "name": user["name"],
        },
    )


async def _account_for(
    platform: Platform, workos: WorkOSClient, user_id: UUID, org_id: str | None
) -> tuple[dict[str, Any] | None, str | None]:
    async with platform.pool.connection() as conn:
        if org_id:
            account = await fetch_one(
                conn, "select * from control.account where workos_organization_id = %s", (org_id,)
            )
            if account is None:
                # JIT: an organization created in WorkOS directly becomes an account.
                org = await workos.get_organization(org_id)
                account = await provision_account(
                    platform,
                    name=org.get("name") or "Account",
                    workos_organization_id=org_id,
                    admin_user_id=user_id,
                )
                return account, "admin"
            m = await fetch_one(
                conn,
                "select role from control.membership where account_id = %s and user_id = %s",
                (account["id"], user_id),
            )
            if m is None:
                # Membership exists in WorkOS (the token proves it): record it as developer.
                async with conn.transaction():
                    await conn.execute(
                        "insert into control.membership (account_id, user_id, role) values (%s, %s, 'developer')"
                        " on conflict do nothing",
                        (account["id"], user_id),
                    )
                return account, "developer"
            return account, m["role"]
        rows = await fetch_all(
            conn,
            """select a.*, m.role from control.membership m join control.account a on a.id = m.account_id
                where m.user_id = %s order by m.created_at""",
            (user_id,),
        )
    if not rows:
        return None, None
    role = rows[0].pop("role")
    return rows[0], role


async def onboard(
    platform: Platform, workos: WorkOSClient | None, principal: Principal, *, account_name: str
) -> dict[str, Any]:
    """First sign-in with no organization: create the WorkOS org, the account, an
    admin membership and the two environments."""
    from securefabric_core import ConflictError

    if principal.account_id is not None:
        raise ConflictError("You already belong to an account.", code="already_onboarded")
    workos_org_id = None
    if workos is not None:
        org = await workos.create_organization(account_name)
        workos_org_id = org["id"]
        try:
            await workos.create_membership(
                user_id=principal.extra["workos_user_id"],
                organization_id=workos_org_id,
                role_slug="admin",
            )
        except UnauthenticatedError:
            await workos.create_membership(
                user_id=principal.extra["workos_user_id"], organization_id=workos_org_id
            )
    return await provision_account(
        platform,
        name=account_name,
        workos_organization_id=workos_org_id,
        admin_user_id=UUID(principal.actor_id),
    )


def dumps(value: Any) -> str:
    return json.dumps(value, default=str)
