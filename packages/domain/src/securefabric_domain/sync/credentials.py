"""Credentials at run time: the DB-backed token cache and the auth provider.

Workers open the vault here and nowhere else. The cached short-lived token is
sealed in ``credential.token_sealed``; refresh is single-flight across processes
under a per-connection advisory lock (AUTH-05); failures are counted once per
calendar day and exhaust after four (AUTH-06).
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from securefabric_cdk.connector import Connector
from securefabric_cdk.tokens import (
    EXHAUSTED_AFTER_DAYS,
    CachedToken,
    ExchangeProvider,
    MultiScheme,
    RefreshState,
    StaticSecret,
)
from securefabric_core.clock import Clock
from securefabric_core.redact import register_secret
from securefabric_db import fetch_one, tenant_tx
from securefabric_domain.runtime import Platform
from securefabric_domain.vault import open_for, open_vendor_app_secrets, seal_for

# In-process single-flight: one coroutine per process waits on the database lock,
# so fifty readers in one worker do not hold fifty pooled connections.
_LOCAL_LOCKS: dict[str, asyncio.Lock] = {}


class DbCredentialStore:
    def __init__(
        self,
        platform: Platform,
        *,
        environment_id: UUID,
        connection_id: UUID,
        clock: Clock,
        scheme: str = "default",
    ) -> None:
        self._p = platform
        self._scheme = scheme
        self._env = environment_id
        self._conn_id = connection_id
        self._clock = clock
        self._cache: dict[str, CachedToken] | None = None

    @asynccontextmanager
    async def _locked(self) -> AsyncIterator[None]:
        local = _LOCAL_LOCKS.setdefault(f"{self._conn_id}:{self._scheme}", asyncio.Lock())
        async with local, self._p.pool.connection() as conn:
            # One lock per scheme: GitHub's installation-token exchange needs the app
            # scheme while it holds its own lock, and session advisory locks on two
            # pooled connections are not reentrant.
            key = f"credential:{self._conn_id}:{self._scheme}"
            await conn.execute("select pg_advisory_lock(hashtextextended(%s, 0))", (key,))
            try:
                self._cache = None  # re-read under the lock
                yield
            finally:
                await conn.execute("select pg_advisory_unlock(hashtextextended(%s, 0))", (key,))

    def lock(self) -> AbstractAsyncContextManager[None]:
        return self._locked()

    async def _tokens(self) -> dict[str, CachedToken]:
        if self._cache is not None:
            return self._cache
        async with tenant_tx(self._p.pool, self._env) as conn:
            row = await fetch_one(
                conn,
                "select token_sealed, vault_key_version from control.credential where connection_id = %s",
                (self._conn_id,),
            )
            tokens: dict[str, CachedToken] = {}
            if row and row["token_sealed"]:
                raw = await open_for(
                    self._p,
                    conn,
                    self._env,
                    row["token_sealed"],
                    version=row["vault_key_version"],
                    connection_id=self._conn_id,
                    purpose="token",
                )
                for scheme, t in raw.items():
                    tokens[scheme] = CachedToken(
                        access_token=t["access_token"],
                        expires_at=datetime.fromisoformat(t["expires_at"])
                        if t.get("expires_at")
                        else None,
                        refresh_token=t.get("refresh_token"),
                        extra=t.get("extra") or {},
                    )
                    register_secret(t["access_token"])
        self._cache = tokens
        return tokens

    async def load_token(self, scheme: str) -> CachedToken | None:
        return (await self._tokens()).get(scheme)

    async def save_token(self, scheme: str, token: CachedToken) -> None:
        register_secret(token.access_token)
        self._cache = None  # merge with what other schemes saved meanwhile
        tokens = dict(await self._tokens())
        tokens[scheme] = token
        payload = {
            s: {
                "access_token": t.access_token,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                "refresh_token": t.refresh_token,
                "extra": t.extra,
            }
            for s, t in tokens.items()
        }
        async with tenant_tx(self._p.pool, self._env) as conn:
            sealed, version = await seal_for(
                conn, self._env, connection_id=self._conn_id, purpose="token", payload=payload
            )
            earliest = min((t.expires_at for t in tokens.values() if t.expires_at), default=None)
            await conn.execute(
                """update control.credential set token_sealed = %s, vault_key_version = %s, token_expires_at = %s,
                          updated_at = now() where connection_id = %s""",
                (sealed, version, earliest, self._conn_id),
            )
            # A rotated refresh token is the new long-lived secret (single-use refresh tokens).
            if token.refresh_token and token.extra.get("rotated_refresh"):
                creds = await self._credentials(conn)
                creds["refresh_token"] = token.refresh_token
                sealed_c, v = await seal_for(
                    conn,
                    self._env,
                    connection_id=self._conn_id,
                    purpose="credential",
                    payload=creds,
                )
                await conn.execute(
                    "update control.credential set sealed = %s, vault_key_version = %s where connection_id = %s",
                    (sealed_c, v, self._conn_id),
                )
        self._cache = tokens

    async def _credentials(self, conn: Any) -> dict[str, Any]:
        row = await fetch_one(
            conn,
            "select sealed, vault_key_version from control.credential where connection_id = %s",
            (self._conn_id,),
        )
        if not row or not row["sealed"]:
            return {}
        result: dict[str, Any] = await open_for(
            self._p,
            conn,
            self._env,
            row["sealed"],
            version=row["vault_key_version"],
            connection_id=self._conn_id,
            purpose="credential",
        )
        return result

    async def refresh_state(self) -> RefreshState:
        async with tenant_tx(self._p.pool, self._env) as conn:
            row = await fetch_one(
                conn,
                "select last_refresh_failure_at, refresh_exhausted from control.credential "
                "where connection_id = %s",
                (self._conn_id,),
            )
        if row is None:
            return RefreshState()
        return RefreshState(
            last_failure_at=row["last_refresh_failure_at"], exhausted=bool(row["refresh_exhausted"])
        )

    async def record_failure(self, error: str) -> RefreshState:
        today = self._clock.now().date()
        async with tenant_tx(self._p.pool, self._env) as conn:
            row = await fetch_one(
                conn,
                """update control.credential
                      set last_refresh_failure_at = %s,
                          refresh_fail_days = case when last_refresh_fail_day = %s then refresh_fail_days
                                                   else refresh_fail_days + 1 end,
                          last_refresh_fail_day = %s,
                          refresh_exhausted = (case when last_refresh_fail_day = %s then refresh_fail_days
                                                    else refresh_fail_days + 1 end) >= %s,
                          updated_at = now()
                    where connection_id = %s
                returning last_refresh_failure_at, refresh_exhausted""",
                (self._clock.now(), today, today, today, EXHAUSTED_AFTER_DAYS, self._conn_id),
            )
        if row is None:
            return RefreshState(last_failure_at=self._clock.now())
        return RefreshState(
            last_failure_at=row["last_refresh_failure_at"], exhausted=bool(row["refresh_exhausted"])
        )

    async def record_success(self) -> None:
        async with tenant_tx(self._p.pool, self._env) as conn:
            await conn.execute(
                """update control.credential set last_refresh_at = %s, refresh_fail_days = 0, refresh_exhausted = false,
                          last_refresh_failure_at = null, last_refresh_fail_day = null where connection_id = %s""",
                (self._clock.now(), self._conn_id),
            )


async def open_credentials(
    platform: Platform, environment_id: UUID, connection_id: UUID
) -> dict[str, Any]:
    async with tenant_tx(platform.pool, environment_id) as conn:
        row = await fetch_one(
            conn,
            "select sealed, vault_key_version from control.credential where connection_id = %s",
            (connection_id,),
        )
        if not row or not row["sealed"]:
            return {}
        creds: dict[str, Any] = await open_for(
            platform,
            conn,
            environment_id,
            row["sealed"],
            version=row["vault_key_version"],
            connection_id=connection_id,
            purpose="credential",
        )
    for v in creds.values():
        if isinstance(v, str):
            register_secret(v)
    return creds


async def build_auth(
    platform: Platform,
    connector: Connector,
    *,
    environment_id: UUID,
    connection_id: UUID,
    vendor_app: dict[str, Any] | None,
    config: dict[str, Any],
    http: Any,
    clock: Clock,
    credentials_override: dict[str, Any] | None = None,
) -> Any:
    credentials = (
        credentials_override
        if credentials_override is not None
        else await open_credentials(platform, environment_id, connection_id)
    )
    vendor_secrets: dict[str, Any] = {}
    if vendor_app is not None:
        async with tenant_tx(platform.pool, environment_id) as conn:
            vendor_secrets = await open_vendor_app_secrets(platform, conn, vendor_app)
        for v in vendor_secrets.values():
            if isinstance(v, str):
                register_secret(v)
    plan = connector.auth_plan(
        credentials=credentials,
        vendor_secrets=vendor_secrets,
        vendor_config=(vendor_app or {}).get("config") or {},
        config=config,
        http=http,
    )
    if plan.static_headers is not None:
        for v in plan.static_headers.values():
            register_secret(v.split(" ", 1)[-1])
        return StaticSecret(plan.static_headers)
    providers = {
        scheme: ExchangeProvider(
            DbCredentialStore(
                platform,
                environment_id=environment_id,
                connection_id=connection_id,
                clock=clock,
                scheme=scheme,
            ),
            {scheme: exchange},
            clock=clock,
            margin=timedelta(seconds=plan.margins_s.get(scheme, 900)),
        )
        for scheme, exchange in plan.exchanges.items()
    }
    return MultiScheme(providers)


def dumps(value: Any) -> str:
    return json.dumps(value, default=str)
