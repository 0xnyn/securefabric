"""Token providers (docs/plan/03-tenancy-connections-vault.md, section 5).

Every connector's auth resolves to a provider with one method,
``material(scheme, force_refresh) -> AuthMaterial``. All providers share one
refresh discipline (AUTH-05, AUTH-06):

1. Use the cached token if it has more than the refresh margin left.
2. Otherwise take the connection's lock, re-read the cache, and refresh only if
   still needed: fifty concurrent readers cause one vendor call.
3. On failure, wait at least 30 seconds before another attempt; the store counts
   failing days once per calendar day and marks the credential exhausted after 4.

The :class:`CredentialStore` port is implemented by the platform (Postgres
advisory lock + ``control.credential``) and in memory for tests.
"""

import asyncio
import base64
import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from securefabric_cdk.errors import AuthRejected, ReauthorizationRequired, VendorUnavailable
from securefabric_cdk.types import AuthMaterial
from securefabric_core.clock import SYSTEM_CLOCK, Clock

MIN_RETRY_AFTER_FAILURE = timedelta(seconds=30)
EXHAUSTED_AFTER_DAYS = 4


@dataclass
class CachedToken:
    access_token: str
    expires_at: datetime | None
    refresh_token: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RefreshState:
    last_failure_at: datetime | None = None
    exhausted: bool = False


class CredentialStore(Protocol):
    """Cache and lock for one connection's credential."""

    def lock(self) -> AbstractAsyncContextManager[None]: ...

    async def load_token(self, scheme: str) -> CachedToken | None: ...

    async def save_token(self, scheme: str, token: CachedToken) -> None: ...

    async def refresh_state(self) -> RefreshState: ...

    async def record_failure(self, error: str) -> RefreshState: ...

    async def record_success(self) -> None: ...


def fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


class TokenProvider:
    def __init__(
        self, store: CredentialStore, *, clock: Clock = SYSTEM_CLOCK, margin: timedelta
    ) -> None:
        self._store = store
        self._clock = clock
        self._margin = margin

    async def material(
        self, scheme: str = "default", *, force_refresh: bool = False
    ) -> AuthMaterial:
        before = await self._store.load_token(scheme)
        if before is not None and not force_refresh and self._fresh(before):
            return self.to_material(before)
        async with self._store.lock():
            token = await self._store.load_token(scheme)  # re-read under the lock
            if token is not None and self._fresh(token):
                if not force_refresh:
                    return self.to_material(token)
                # A forced refresh re-mints only if nobody replaced the token that
                # failed while we waited: concurrent 401s collapse into one refresh.
                if before is not None and token.access_token != before.access_token:
                    return self.to_material(token)
            state = await self._store.refresh_state()
            if state.exhausted:
                raise ReauthorizationRequired("token refresh is exhausted")
            if (
                state.last_failure_at
                and self._clock.now() - state.last_failure_at < MIN_RETRY_AFTER_FAILURE
            ):
                if token is not None and self._usable(token):
                    return self.to_material(token)
                raise VendorUnavailable("token refresh failed recently; waiting before retrying")
            try:
                new = await self.refresh(scheme, token)
            except AuthRejected as exc:
                after = await self._store.record_failure(str(exc))
                if after.exhausted:
                    raise ReauthorizationRequired(str(exc)) from exc
                raise
            except VendorUnavailable as exc:
                await self._store.record_failure(str(exc))
                raise
            await self._store.save_token(scheme, new)
            await self._store.record_success()
            return self.to_material(new)

    def _fresh(self, token: CachedToken) -> bool:
        return token.expires_at is None or token.expires_at - self._clock.now() > self._margin

    def _usable(self, token: CachedToken) -> bool:
        return token.expires_at is None or token.expires_at > self._clock.now()

    def to_material(self, token: CachedToken) -> AuthMaterial:
        return AuthMaterial(
            headers={"Authorization": f"Bearer {token.access_token}"},
            expires_at=token.expires_at,
            fingerprint=fingerprint(token.access_token),
        )

    async def refresh(self, scheme: str, current: CachedToken | None) -> CachedToken:
        raise NotImplementedError


class StaticSecret:
    """API key or basic auth: the sealed secret is the material."""

    def __init__(self, headers: dict[str, str]) -> None:
        self._headers = headers
        self._fp = fingerprint(repr(sorted(headers.items())))

    @classmethod
    def api_key(
        cls, key: str, *, header: str = "Authorization", prefix: str = "Bearer "
    ) -> "StaticSecret":
        return cls({header: f"{prefix}{key}"})

    @classmethod
    def basic(cls, username: str, password: str) -> "StaticSecret":
        raw = base64.b64encode(f"{username}:{password}".encode()).decode()
        return cls({"Authorization": f"Basic {raw}"})

    async def material(
        self, scheme: str = "default", *, force_refresh: bool = False
    ) -> AuthMaterial:
        return AuthMaterial(headers=dict(self._headers), fingerprint=self._fp)


type Exchange = Callable[[CachedToken | None], Awaitable[CachedToken]]


class ExchangeProvider(TokenProvider):
    """A provider whose refresh is a callable: OAuth2 refresh, client credentials,
    GitHub installation tokens. The callable does the vendor HTTP exchange and
    raises :class:`AuthRejected` or :class:`VendorUnavailable`."""

    def __init__(
        self,
        store: CredentialStore,
        exchanges: dict[str, Exchange],
        *,
        clock: Clock = SYSTEM_CLOCK,
        margin: timedelta = timedelta(minutes=15),
        header: Callable[[CachedToken], dict[str, str]] | None = None,
    ) -> None:
        super().__init__(store, clock=clock, margin=margin)
        self._exchanges = exchanges
        self._header = header

    async def refresh(self, scheme: str, current: CachedToken | None) -> CachedToken:
        try:
            exchange = self._exchanges[scheme]
        except KeyError:
            raise AuthRejected(f"no auth scheme {scheme!r}") from None
        return await exchange(current)

    def to_material(self, token: CachedToken) -> AuthMaterial:
        if self._header is None:
            return super().to_material(token)
        return AuthMaterial(
            headers=self._header(token),
            expires_at=token.expires_at,
            fingerprint=fingerprint(token.access_token),
        )


class MultiScheme:
    """Routes schemes to different providers (GitHub: app JWT vs installation token)."""

    def __init__(self, providers: dict[str, Any]) -> None:
        self._providers = providers

    async def material(
        self, scheme: str = "default", *, force_refresh: bool = False
    ) -> AuthMaterial:
        provider = self._providers.get(scheme) or self._providers["default"]
        result: AuthMaterial = await provider.material(scheme, force_refresh=force_refresh)
        return result


class MemoryCredentialStore:
    """In-process store for tests and dry runs."""

    def __init__(self, clock: Clock = SYSTEM_CLOCK) -> None:
        self._lock = asyncio.Lock()
        self._tokens: dict[str, CachedToken] = {}
        self._state = RefreshState()
        self._clock = clock
        self.fail_days: set[str] = set()
        self.refreshes = 0

    @asynccontextmanager
    async def _locked(self) -> AsyncIterator[None]:
        async with self._lock:
            yield

    def lock(self) -> AbstractAsyncContextManager[None]:
        return self._locked()

    async def load_token(self, scheme: str) -> CachedToken | None:
        return self._tokens.get(scheme)

    async def save_token(self, scheme: str, token: CachedToken) -> None:
        self.refreshes += 1
        self._tokens[scheme] = token

    async def refresh_state(self) -> RefreshState:
        return self._state

    async def record_failure(self, error: str) -> RefreshState:
        now = self._clock.now()
        self.fail_days.add(now.date().isoformat())
        self._state = RefreshState(
            last_failure_at=now, exhausted=len(self.fail_days) >= EXHAUSTED_AFTER_DAYS
        )
        return self._state

    async def record_success(self) -> None:
        self.fail_days.clear()
        self._state = RefreshState()
