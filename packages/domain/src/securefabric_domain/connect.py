"""The connect flow (part 3, section 8; part 6, section 3).

- A **connect session** is an invite token scoped to one organization and a list
  of integrations, valid 30 minutes, stored hashed, single use for creation
  (reuse or expiry is 410).
- **Redirect connectors** (GitHub) get an ``authorize_url`` carrying a random,
  single-use ``state`` (10 minutes).

The installation binding rule: *an installation id is never trusted from a URL*.
The callback (API) only consumes ``state`` and seals the OAuth ``code``; a
control worker (which alone can open the app's client secret) exchanges it for
a user token, lists ``GET /user/installations``, and binds only if the
installation from the URL is in that list. The user token is discarded.
"""

import json
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode, urlsplit
from uuid import UUID

import httpx2

from securefabric_cdk import oauth2
from securefabric_core import (
    BadRequestError,
    GoneError,
    NotFoundError,
    UnauthenticatedError,
    ValidationFailedError,
    get_logger,
)
from securefabric_core.crypto import random_token, sha256
from securefabric_db import Conn, fetch_all, fetch_one, fetch_required, tenant_tx
from securefabric_domain.catalog import connector_public, get_integration_row, resolve_vendor_app
from securefabric_domain.runtime import Platform
from securefabric_domain.tenancy import Principal, audit
from securefabric_domain.vault import open_for, open_vendor_app_secrets, seal_for
from securefabric_schema import AuthMode
from securefabric_tasks.spec import spawn_sql

log = get_logger(__name__)

SESSION_TTL = timedelta(minutes=30)
STATE_TTL = timedelta(minutes=10)
TOKEN_PREFIX = "sfcs_"  # noqa: S105
CONNECT_SCOPES = frozenset({"provisioning:read", "provisioning:write"})


def _origin(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}".lower()


async def _check_redirect(conn: Conn, environment_id: UUID, url: str | None, field: str) -> None:
    if not url:
        return
    env = await fetch_one(
        conn, "select settings from control.environment where id = %s", (environment_id,)
    )
    allowed = {
        _origin(o) for o in ((env or {}).get("settings") or {}).get("allowed_redirect_origins", [])
    }
    if _origin(url) not in allowed:
        raise ValidationFailedError(
            f"{field} must be on one of the environment's allowed redirect origins",
            code="redirect_not_allowed",
            errors=[{"field": field, "message": "origin not allowed"}],
        )


# ---------------------------------------------------------------- sessions (CON-06, CON-08)


async def create_session(
    platform: Platform,
    principal: Principal,
    *,
    organization_id: UUID,
    integrations: list[str] | None,
    connection_id: UUID | None,
    option_presets: dict[str, Any] | None,
    redirect_success: str | None,
    redirect_error: str | None,
) -> dict[str, Any]:
    principal.require("provisioning:write")
    env = principal.env
    token = TOKEN_PREFIX + random_token(32)
    async with tenant_tx(platform.pool, env) as conn:
        org = await fetch_one(
            conn,
            "select id from control.organization where id = %s and deleted_at is null",
            (organization_id,),
        )
        if org is None:
            raise NotFoundError("Organization not found", code="organization_not_found")
        ids: list[UUID] = []
        for ref in integrations or []:
            try:
                row = await get_integration_row(conn, ref)
            except NotFoundError:
                from securefabric_domain.catalog import ensure_default_integration

                row = await ensure_default_integration(platform, conn, env, ref.upper())
            ids.append(row["id"])
        if connection_id is not None:
            c = await fetch_one(
                conn,
                "select organization_id, integration_id from control.connection where id = %s and deleted_at is null",
                (connection_id,),
            )
            if c is None or c["organization_id"] != organization_id:
                raise NotFoundError("Connection not found", code="connection_not_found")
            ids = [c["integration_id"]]
        await _check_redirect(conn, env, redirect_success, "redirect_success")
        await _check_redirect(conn, env, redirect_error, "redirect_error")
        now = platform.clock.now()
        row = await fetch_required(
            conn,
            """insert into control.connect_session (environment_id, organization_id, token_hash,
              allowed_integration_ids,
                   connection_id, option_presets, redirect_success, redirect_error, expires_at)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning id, expires_at, created_at""",
            (
                env,
                organization_id,
                sha256(token),
                ids,
                connection_id,
                json.dumps(option_presets or {}),
                redirect_success,
                redirect_error,
                now + SESSION_TTL,
            ),
        )
        assert row is not None
        await audit(
            conn,
            principal,
            "connect_session.created",
            target_kind="connect_session",
            target_id=row["id"],
            detail={
                "organization_id": str(organization_id),
                "reauthorize": connection_id is not None,
            },
        )
    url = f"{platform.settings.public_dash_url.rstrip('/')}/connect/{token}"
    return {
        "id": row["id"],
        "token": token,
        "url": url,
        "expires_at": row["expires_at"],
        "organization_id": organization_id,
        "connection_id": connection_id,
    }


async def list_sessions(
    platform: Platform, principal: Principal, organization_id: UUID | None = None
) -> list[dict[str, Any]]:
    principal.require("provisioning:read")
    async with tenant_tx(platform.pool, principal.env) as conn:
        return await fetch_all(
            conn,
            """select id, organization_id, allowed_integration_ids, connection_id, redirect_success, redirect_error,
                      expires_at, used_at, created_at from control.connect_session
                where (%s::uuid is null or organization_id = %s) order by created_at desc limit 200""",
            (organization_id, organization_id),
        )


async def authenticate_session_token(platform: Platform, token: str) -> Principal:
    if not token.startswith(TOKEN_PREFIX):
        raise UnauthenticatedError("Invalid connect session token.", code="invalid_connect_session")
    async with platform.pool.connection() as conn:
        row = await fetch_one(
            conn, "select * from control.resolve_connect_session(%s)", (sha256(token),)
        )
    if row is None:
        raise UnauthenticatedError("Invalid connect session token.", code="invalid_connect_session")
    if row["expires_at"] <= platform.clock.now():
        raise GoneError("This connect link has expired.", code="connect_session_expired")
    return Principal(
        kind="connect_session",
        account_id=row["account_id"],
        environment_id=row["environment_id"],
        scopes=CONNECT_SCOPES,
        actor_id=str(row["id"]),
        organization_id=row["organization_id"],
        extra={"session_id": row["id"], "used": row["used_at"] is not None},
    )


async def session_view(platform: Platform, principal: Principal) -> dict[str, Any]:
    """``GET /v1/connect/session``: what the connect UI renders."""
    async with tenant_tx(platform.pool, principal.env) as conn:
        s = await fetch_one(
            conn,
            "select * from control.connect_session where id = %s",
            (principal.extra["session_id"],),
        )
        assert s is not None
        env = await fetch_one(
            conn, "select name, settings from control.environment where id = %s", (principal.env,)
        )
        org = await fetch_one(
            conn,
            "select id, name, identifier from control.organization where id = %s",
            (s["organization_id"],),
        )
        if s["allowed_integration_ids"]:
            integs = await fetch_all(
                conn,
                "select * from control.integration where id = any(%s) and deleted_at is null",
                (s["allowed_integration_ids"],),
            )
        else:
            integs = await fetch_all(
                conn,
                "select * from control.integration where deleted_at is null order by created_at",
            )
    out = []
    for i in integs:
        manifest = platform.registry.manifest(i["connector_id"])
        pub = connector_public(manifest)
        out.append(
            {"id": i["id"], "key": i["key"], "display_name": i["display_name"], "connector": pub}
        )
    settings = (env or {}).get("settings") or {}
    return {
        "id": s["id"],
        "organization": org,
        "expires_at": s["expires_at"],
        "used_at": s["used_at"],
        "reauthorize_connection_id": s["connection_id"],
        "option_presets": s["option_presets"],
        "integrations": out,
        "branding": {**(settings.get("connect_ui") or {}), "environment": (env or {}).get("name")},
        "redirect_success": s["redirect_success"],
        "redirect_error": s["redirect_error"],
    }


async def mark_used(conn: Conn, principal: Principal) -> None:
    row = await fetch_one(
        conn,
        "update control.connect_session set used_at = now() where id = %s and used_at is null returning id",
        (principal.extra["session_id"],),
    )
    if row is None:
        raise GoneError("This connect link was already used.", code="connect_session_used")


async def connect_create(
    platform: Platform,
    principal: Principal,
    *,
    integration: str,
    credentials: dict[str, Any] | None,
    options: dict[str, Any] | None,
    mode: str = "install",
) -> dict[str, Any]:
    """``POST /v1/connect/connections``: one connection per session (single use)."""
    from securefabric_domain.connections import create_connection, get_row

    async with tenant_tx(platform.pool, principal.env) as conn:
        s = await fetch_one(
            conn,
            "select * from control.connect_session where id = %s",
            (principal.extra["session_id"],),
        )
        assert s is not None
        row = await get_integration_row(conn, integration)
        if s["allowed_integration_ids"] and row["id"] not in s["allowed_integration_ids"]:
            raise NotFoundError(
                "Integration not offered by this session", code="integration_not_found"
            )
        reauth = s["connection_id"]
    presets = s["option_presets"] or {}
    if reauth is not None:
        # CON-09: re-authorise the same connection; ids, history and data unchanged.
        async with tenant_tx(platform.pool, principal.env) as conn:
            await mark_used(conn, principal)
            existing = await get_row(conn, reauth)
            integ = await get_integration_row(conn, str(existing["integration_id"]))
            manifest = platform.registry.manifest(integ["connector_id"])
            if manifest.auth.connect.value == "redirect":
                url = await begin_redirect(
                    platform,
                    conn,
                    principal,
                    connection=existing,
                    integration=integ,
                    connect_session_id=s["id"],
                    kind=mode,
                )
                return {"id": reauth, "state": existing["state"], "authorize_url": url}
            from securefabric_domain.connections import spawn_verify, validate_credentials

            creds = validate_credentials(platform, manifest.id, credentials or {})
            sealed, version = await seal_for(
                conn, principal.env, connection_id=reauth, purpose="credential", payload=creds
            )
            await conn.execute(
                "update control.credential set staged_sealed = %s, vault_key_version = %s where connection_id = %s",
                (sealed, version, reauth),
            )
            await spawn_verify(conn, principal.env, reauth, "rotate", staged=True)
            return {"id": reauth, "state": existing["state"], "authorize_url": None}
    async with tenant_tx(platform.pool, principal.env) as conn:
        await mark_used(conn, principal)
    try:
        created = await create_connection(
            platform,
            principal,
            organization_id=s["organization_id"],
            integration=str(row["id"]),
            credentials=credentials,
            options={**presets, **(options or {})},
            connect_session_id=s["id"],
        )
    except Exception:
        async with tenant_tx(
            platform.pool, principal.env
        ) as conn:  # a failed create does not burn the link
            await conn.execute(
                "update control.connect_session set used_at = null where id = %s", (s["id"],)
            )
        raise
    return {
        "id": created["id"],
        "state": created["state"],
        "authorize_url": created.get("authorize_url"),
    }


async def connect_status(
    platform: Platform, principal: Principal, connection_id: UUID
) -> dict[str, Any]:
    async with tenant_tx(platform.pool, principal.env) as conn:
        row = await fetch_one(
            conn,
            """select id, state, health_code, health_details, pending_detail, organization_id
                                         from control.connection where id = %s""",
            (connection_id,),
        )
        if row is None or row["organization_id"] != principal.organization_id:
            raise NotFoundError("Connection not found", code="connection_not_found")
        grants = await fetch_all(
            conn,
            "select stream, status, detail from control.connection_grant where connection_id = %s",
            (connection_id,),
        )
        # The latest verification (create, rotate, test, ...): how the connect UI tells a
        # rotation that was accepted from one that was rejected and discarded.
        last = await fetch_one(
            conn,
            """select action, status, summary, started_at from obs.operation
                where connection_id = %s and kind = 'auth' and action like 'verify:%%'
                order by started_at desc limit 1""",
            (connection_id,),
        )
    verification = None
    if last is not None:
        summary = last["summary"] or {}
        verification = {
            "reason": last["action"].split(":", 1)[1],
            "status": last["status"],
            "message": summary.get("error")
            if last["status"] == "failed"
            else summary.get("tenant"),
            "at": last["started_at"],
        }
    return {
        "id": row["id"],
        "state": row["state"],
        "health_code": row["health_code"],
        "pending_detail": row["pending_detail"],
        "grants": grants,
        "missing_permissions": [g["stream"] for g in grants if g["status"] == "UNAUTHORIZED"],
        "last_verification": verification,
    }


# ---------------------------------------------------------------- redirect (GitHub App install)


def callback_url(platform: Platform, connector_id: str) -> str:
    api = platform.settings.public_api_url.rstrip("/")
    return f"{api}/v1/connect/callback/{connector_id.lower()}"


def _authorize_endpoint(platform: Platform, connector_id: str, base: str, url: str) -> str:
    """Absolute, relative to the vendor app's base URL, or ``local:/path``: served by
    the platform through the connector's in-process vendor (SANDBOX has no website)."""
    if url.startswith("local:"):
        api = platform.settings.public_api_url.rstrip("/")
        return f"{api}/v1/connect/local/{connector_id.lower()}{url.removeprefix('local:')}"
    if url.startswith(("https://", "http://")):
        return url
    return f"{base}/{url.lstrip('/')}"


async def begin_redirect(
    platform: Platform,
    conn: Conn,
    principal: Principal,
    *,
    connection: dict[str, Any],
    integration: dict[str, Any],
    connect_session_id: UUID | None,
    kind: str = "install",
) -> str:
    app = await resolve_vendor_app(conn, integration)
    if app is None:
        raise ValidationFailedError(
            "No vendor app is registered for this connector.", code="vendor_app_missing"
        )
    state = random_token(32)  # 256 bits
    if connect_session_id is None:
        # Direct API creation (CON-01): an implicit single-use session for the redirect.
        s = await fetch_one(
            conn,
            """insert into control.connect_session (environment_id, organization_id, token_hash,
              allowed_integration_ids,
                   connection_id, expires_at, used_at) values (%s, %s, %s, %s, %s, %s, now()) returning id""",
            (
                connection["environment_id"],
                connection["organization_id"],
                sha256(random_token(32)),
                [integration["id"]],
                connection["id"],
                platform.clock.now() + SESSION_TTL,
            ),
        )
        assert s is not None
        connect_session_id = s["id"]
    manifest = platform.registry.manifest(connection["connector_id"])
    oauth = manifest.auth.oauth2 if manifest.auth.mode is AuthMode.OAUTH2 else None
    pkce = oauth2.pkce_pair() if oauth is not None and oauth.pkce else None
    await conn.execute(
        """insert into control.oauth_state (state, environment_id, connect_session_id, connection_id, vendor_app_id,
          kind, code_verifier, expires_at) values (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            state,
            connection["environment_id"],
            connect_session_id,
            connection["id"],
            app["id"],
            "oauth2" if oauth is not None else kind,
            pkce.verifier if pkce else None,
            platform.clock.now() + STATE_TTL,
        ),
    )
    base = app["base_url"].rstrip("/")
    cfg = app["config"] or {}
    if oauth is not None and oauth.authorize_url:
        # Standard OAuth2 authorization code (+ PKCE S256), from the manifest alone.
        return oauth2.authorize_url(
            _authorize_endpoint(platform, connection["connector_id"], base, oauth.authorize_url),
            client_id=str(cfg.get("client_id")),
            redirect_uri=callback_url(platform, connection["connector_id"]),
            state=state,
            scopes=oauth.scopes,
            pkce=pkce,
        )
    if kind == "authorize":
        # "I already installed it": plain OAuth, then pick an installation.
        return f"{base}/login/oauth/authorize?" + urlencode(
            {
                "client_id": cfg.get("client_id"),
                "state": state,
                "redirect_uri": callback_url(platform, connection["connector_id"]),
            }
        )
    return f"{base}/apps/{cfg.get('slug')}/installations/new?" + urlencode({"state": state})


async def handle_callback(
    platform: Platform, connector: str, params: dict[str, str]
) -> tuple[str, UUID | None]:
    """API side of the redirect: consume ``state`` (single use, 10 min), seal the
    code, and hand off to a control worker. Returns (redirect URL, connection id)."""
    dash = platform.settings.public_dash_url.rstrip("/")
    state = params.get("state")
    if not state:
        # Installed from GitHub's own UI: nothing to bind.
        return f"{dash}/connect/done?status=no_state", None
    async with platform.pool.connection() as conn:
        st = await fetch_one(conn, "select * from control.resolve_oauth_state(%s)", (state,))
    if st is None or st["consumed_at"] is not None or st["expires_at"] <= platform.clock.now():
        return f"{dash}/connect/done?status=expired", None
    env = st["environment_id"]
    async with tenant_tx(platform.pool, env) as conn:
        consumed = await fetch_one(
            conn,
            "update control.oauth_state set consumed_at = now() where state = %s and consumed_at is null returning "
            "state",
            (state,),
        )
        if consumed is None:
            return f"{dash}/connect/done?status=expired", None
        session = await fetch_one(
            conn, "select * from control.connect_session where id = %s", (st["connect_session_id"],)
        )
        if params.get("error"):
            await _fail_pending(
                conn,
                st["connection_id"],
                f"authorization denied: {params.get('error_description') or params['error']}",
            )
            return _redirect(dash, session, "error", st["connection_id"], "denied"), st[
                "connection_id"
            ]
        if params.get("setup_action") == "request":
            await conn.execute(
                "update control.connection set pending_detail = %s, connection_config = connection_config || %s "
                "where id = %s",
                (
                    "waiting for an organization owner to approve the installation request",
                    json.dumps({"install_requested": True}),
                    st["connection_id"],
                ),
            )
            return _redirect(dash, session, "success", st["connection_id"], "requested"), st[
                "connection_id"
            ]
        if not params.get("code"):
            await _fail_pending(
                conn, st["connection_id"], "the vendor did not return an authorization code"
            )
            return _redirect(dash, session, "error", st["connection_id"], "no_code"), st[
                "connection_id"
            ]
        sealed, version = await seal_for(
            conn,
            env,
            connection_id=st["connection_id"],
            purpose="oauth_callback",
            payload={
                "code": params["code"],
                "installation_id": params.get("installation_id"),
                "setup_action": params.get("setup_action"),
            },
        )
        await conn.execute(
            "update control.oauth_state set callback_sealed = %s, callback_key_version = %s where state = %s",
            (sealed, version, state),
        )
        await spawn_sql(
            conn,
            queue="control",
            task_name="connect.complete",
            params={"state": state, "environment_id": str(env)},
            idempotency_key=f"connect:{state}",
        )
    return _redirect(dash, session, "success", st["connection_id"], "verifying"), st[
        "connection_id"
    ]


def _redirect(
    dash: str, session: dict[str, Any] | None, outcome: str, connection_id: UUID | None, status: str
) -> str:
    target = (session or {}).get("redirect_success" if outcome == "success" else "redirect_error")
    q = urlencode({"connection_id": str(connection_id) if connection_id else "", "status": status})
    if target:
        sep = "&" if "?" in target else "?"
        return f"{target}{sep}{q}"
    return f"{dash}/connect/done?{q}"


async def _fail_pending(conn: Conn, connection_id: UUID | None, message: str) -> None:
    if connection_id is not None:
        await conn.execute(
            "update control.connection set pending_detail = %s where id = %s and state = 'PENDING'",
            (message[:500], connection_id),
        )


async def complete_redirect(
    platform: Platform,
    state: str,
    environment_id: UUID,
    *,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Control worker: exchange the code, list the user's installations, bind only
    if the URL's installation is among them, then verify."""
    from securefabric_domain.connections import verify_connection

    async with tenant_tx(platform.pool, environment_id) as conn:
        st = await fetch_one(conn, "select * from control.oauth_state where state = %s", (state,))
        if st is None or not st["callback_sealed"]:
            raise BadRequestError("unknown or incomplete connect state")
        payload = await open_for(
            platform,
            conn,
            environment_id,
            st["callback_sealed"],
            version=st["callback_key_version"] or 1,
            connection_id=st["connection_id"],
            purpose="oauth_callback",
        )
        app = await fetch_one(
            conn, "select * from control.vendor_app where id = %s", (st["vendor_app_id"],)
        )
        assert app is not None
        secrets = await open_vendor_app_secrets(platform, conn, app)
        await conn.execute(
            "update control.oauth_state set callback_sealed = null where state = %s", (state,)
        )
        connection = await fetch_one(
            conn, "select * from control.connection where id = %s", (st["connection_id"],)
        )
        assert connection is not None
    if st["kind"] == "oauth2":
        return await _complete_oauth2(
            platform, environment_id, st, app, secrets, connection, payload, transport
        )
    cfg = app["config"] or {}
    base = app["base_url"].rstrip("/")
    api = (cfg.get("api_base_url") or "https://api.github.com").rstrip("/")
    claimed = payload.get("installation_id")
    async with httpx2.AsyncClient(
        transport=transport or platform.vendor_transport(), timeout=20.0
    ) as http:
        tok = await http.post(
            f"{base}/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": cfg.get("client_id"),
                "client_secret": secrets.get("client_secret"),
                "code": payload["code"],
            },
        )
        body = tok.json() if tok.content else {}
        user_token = body.get("access_token")
        if not user_token:
            return await _reject(
                platform,
                environment_id,
                connection,
                f"code exchange failed: {body.get('error', tok.status_code)}",
                claimed,
            )
        installations: list[dict[str, Any]] = []
        url: str | None = f"{api}/user/installations?per_page=100"
        while url:
            r = await http.get(
                url,
                headers={
                    "Authorization": f"Bearer {user_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            if r.status_code != 200:
                return await _reject(
                    platform,
                    environment_id,
                    connection,
                    f"could not list installations ({r.status_code})",
                    claimed,
                )
            installations.extend(r.json().get("installations") or [])
            from securefabric_cdk.paginate import parse_link_header

            url = parse_link_header(r.headers.get("link")).get("next")
    del user_token  # never stored
    ids = {str(i["id"]): i for i in installations}
    if claimed is None:
        if len(ids) != 1:
            # "Already installed" path with several installations: the UI lets the user pick.
            async with tenant_tx(platform.pool, environment_id) as conn:
                await conn.execute(
                    "update control.connection set pending_detail = %s, connection_config = connection_config || %s "
                    "where id = %s",
                    (
                        "choose an installation",
                        json.dumps(
                            {
                                "installation_choices": [
                                    {
                                        "id": i["id"],
                                        "account": (i.get("account") or {}).get("login"),
                                    }
                                    for i in installations
                                ]
                            }
                        ),
                        connection["id"],
                    ),
                )
            return {
                "connection_id": str(connection["id"]),
                "is_valid": False,
                "message": "choose an installation",
            }
        claimed = next(iter(ids))
    if str(claimed) not in ids:
        return await _reject(
            platform,
            environment_id,
            connection,
            "the signed-in user cannot access that installation",
            claimed,
            audit_it=True,
        )
    inst = ids[str(claimed)]
    async with tenant_tx(platform.pool, environment_id) as conn:
        await conn.execute(
            """update control.connection set connection_config = connection_config || %s, vendor_tenant_ref = %s,
                      pending_detail = null, updated_at = now() where id = %s""",
            (
                json.dumps(
                    {
                        "installation_id": int(claimed),
                        "account_login": (inst.get("account") or {}).get("login"),
                        "account_id": (inst.get("account") or {}).get("id"),
                        "account_type": (inst.get("account") or {}).get("type"),
                        "repository_selection": inst.get("repository_selection"),
                    }
                ),
                str(claimed),
                connection["id"],
            ),
        )
        from securefabric_domain.tenancy import system_principal

        await audit(
            conn,
            system_principal(environment_id),
            "connect.installation_bound",
            target_kind="connection",
            target_id=connection["id"],
            detail={"installation_id": str(claimed)},
        )
    reason = "create" if connection["state"] == "PENDING" else "reauthorize"
    return await verify_connection(platform, environment_id, connection["id"], reason=reason)


async def _complete_oauth2(
    platform: Platform,
    environment_id: UUID,
    st: dict[str, Any],
    app: dict[str, Any],
    secrets: dict[str, Any],
    connection: dict[str, Any],
    payload: dict[str, Any],
    transport: httpx2.AsyncBaseTransport | None,
) -> dict[str, Any]:
    """Exchange the code (with the PKCE verifier), keep only the refresh token
    (sealed as the credential), cache the access token, then verify."""
    from securefabric_cdk.errors import ConnectorError
    from securefabric_cdk.http import HttpClient
    from securefabric_cdk.tokens import CachedToken
    from securefabric_domain.connections import verify_connection
    from securefabric_domain.sync.credentials import DbCredentialStore

    connector = platform.registry.get(connection["connector_id"])
    manifest = connector.manifest
    assert manifest.auth.oauth2 is not None
    config = connection["connection_config"] or {}
    http = HttpClient(
        base_url=connector.base_url(config, app),
        transport=transport
        or connector.local_transport(config, connection["options"] or {})
        or platform.vendor_transport(),
        spec=manifest.http,
        clock=platform.clock,
        sleep=platform.sleep,
        scrub_fields=manifest.scrub_fields,
    )
    try:
        token: CachedToken = await oauth2.exchange_code(
            http,
            manifest.auth.oauth2.token_url,
            client_id=str((app["config"] or {}).get("client_id")),
            client_secret=secrets.get("client_secret"),
            code=payload["code"],
            redirect_uri=callback_url(platform, connection["connector_id"]),
            code_verifier=st["code_verifier"],
            now=platform.clock.now(),
        )
    except ConnectorError as exc:
        return await _reject(
            platform, environment_id, connection, f"code exchange failed: {exc.message}", None
        )
    finally:
        await http.aclose()
    if not token.refresh_token:
        return await _reject(
            platform, environment_id, connection, "the vendor issued no refresh token", None
        )
    async with tenant_tx(platform.pool, environment_id) as conn:
        sealed, version = await seal_for(
            conn,
            environment_id,
            connection_id=connection["id"],
            purpose="credential",
            payload={"refresh_token": token.refresh_token},
        )
        # A new authorisation replaces the old one wholesale: fresh refresh failure policy.
        await conn.execute(
            """update control.credential set sealed = %s, vault_key_version = %s,
                      fields_set = array['refresh_token'], token_sealed = null, token_expires_at = null,
                      refresh_exhausted = false, refresh_fail_days = 0, last_refresh_fail_day = null,
                      last_refresh_failure_at = null, rotated_at = now(), updated_at = now()
                where connection_id = %s""",
            (sealed, version, connection["id"]),
        )
        await conn.execute(
            "update control.connection set pending_detail = null, updated_at = now() where id = %s",
            (connection["id"],),
        )
    token.extra["rotated_refresh"] = False  # just sealed above
    await DbCredentialStore(
        platform,
        environment_id=environment_id,
        connection_id=connection["id"],
        clock=platform.clock,
        scheme="default",
    ).save_token("default", token)
    reason = "create" if connection["state"] == "PENDING" else "reauthorize"
    return await verify_connection(platform, environment_id, connection["id"], reason=reason)


async def _reject(
    platform: Platform,
    environment_id: UUID,
    connection: dict[str, Any],
    message: str,
    claimed: Any,
    *,
    audit_it: bool = False,
) -> dict[str, Any]:
    from securefabric_domain.events.outbox import emit
    from securefabric_domain.tenancy import system_principal

    async with tenant_tx(platform.pool, environment_id) as conn:
        await _fail_pending(conn, connection["id"], message)
        if audit_it:
            await audit(
                conn,
                system_principal(environment_id),
                "connect.installation_rejected",
                target_kind="connection",
                target_id=connection["id"],
                detail={"claimed_installation_id": str(claimed), "reason": message},
            )
        if connection["state"] == "PENDING":
            await emit(
                conn,
                environment_id=environment_id,
                connection_id=connection["id"],
                type="connection.create.failed",
                data={
                    "vendor": connection["connector_id"],
                    "error": "UNAUTHORIZED",
                    "description": message,
                },
            )
    log.warning("connect_rejected", connection_id=str(connection["id"]), reason=message)
    return {"connection_id": str(connection["id"]), "is_valid": False, "message": message}


async def local_vendor_page(
    platform: Platform, connector_id: str, path: str, query: dict[str, str]
) -> str:
    """The vendor-side authorize page of a connector whose vendor runs in-process
    (``authorize_url: local:/...``; SANDBOX_OAUTH). Returns where to send the browser.

    Only this connector's own callback is accepted as ``redirect_uri``: the page
    redirects there, so anything else would be an open redirect."""
    connector = platform.registry.get(connector_id)
    oauth = connector.manifest.auth.oauth2
    if oauth is None or not (oauth.authorize_url or "").startswith("local:"):
        raise NotFoundError("Not found", code="not_found")
    if f"/{path.lstrip('/')}" != oauth.authorize_url.removeprefix("local:"):  # type: ignore[union-attr]
        raise NotFoundError("Not found", code="not_found")
    if query.get("redirect_uri") != callback_url(platform, connector.manifest.id):
        raise BadRequestError("redirect_uri is not this connector's callback", code="bad_redirect")
    transport = connector.local_transport({}, {})
    if transport is None:
        raise NotFoundError("Not found", code="not_found")
    base = connector.base_url({}, None)
    async with httpx2.AsyncClient(transport=transport, timeout=10.0) as http:
        resp = await http.get(f"{base}/{path.lstrip('/')}", params=query)
    location = resp.headers.get("location")
    if resp.status_code not in (301, 302, 303) or not location:
        raise BadRequestError(
            "the vendor refused the authorization request", code="authorization_refused"
        )
    return str(location)
