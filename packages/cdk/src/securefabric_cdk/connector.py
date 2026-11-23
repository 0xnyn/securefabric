"""The connector and stream interfaces (docs/plan/05-connector-sdk.md, section 3).

Design rules:

- ``normalize`` is pure: one raw item in, one canonical record (or Skip) out.
  No network, no clock, no randomness. Fixtures, golden tests, re-normalisation
  and sandbox connections all depend on that.
- ``read`` owns pagination and checkpoints, and nothing else. It never writes.
- ``handle_webhook`` is pure too: the connector says what a delivery means,
  the platform does it (PD-11).
"""

from collections.abc import AsyncIterator
from typing import Any, ClassVar

from securefabric_cdk.context import Context
from securefabric_cdk.errors import ConfigInvalid
from securefabric_cdk.manifest import Manifest, StreamSpec
from securefabric_cdk.types import (
    Action,
    ActionResult,
    AuthPlan,
    Checkpoint,
    GoneMarker,
    Grant,
    IngressDelivery,
    NormalizeContext,
    Page,
    RawItem,
    Skip,
    Tombstone,
    VerifyResult,
    WebhookEffect,
)
from securefabric_schema import GrantStatus, Mode, Record


class Stream:
    """Base class for a stream. Subclasses set ``name`` and implement the methods."""

    name: ClassVar[str]
    # Checkpoint keys that survive into a new pass (the incremental watermark).
    # Everything else is the position of one pass and is dropped when a new full
    # pass starts, so it can never resume an older pass's listing (part 4, section 8).
    persistent_checkpoint_keys: ClassVar[tuple[str, ...]] = ("watermark",)

    def __init__(self, connector: "Connector") -> None:
        self.connector = connector

    def fresh_checkpoint(self, previous: Checkpoint) -> Checkpoint:
        return {k: v for k, v in (previous or {}).items() if k in self.persistent_checkpoint_keys}

    @property
    def spec(self) -> StreamSpec:
        return self.connector.manifest.stream(self.name)

    def read(self, ctx: Context, checkpoint: Checkpoint, mode: Mode) -> AsyncIterator[Page]:
        raise NotImplementedError

    async def read_one(self, ctx: Context, key: str) -> RawItem | GoneMarker:
        raise NotImplementedError(f"{self.name} does not support targeted refresh")

    def normalize(self, raw: RawItem, nctx: NormalizeContext) -> Record | Skip | Tombstone:
        raise NotImplementedError


class ExportStream(Stream):
    """Async vendor exports (SYNC-16): request, poll, download chunks.

    The engine drives the loop and checkpoints the export id and completed
    chunks, parking the run between polls (part 4, section 11).
    """

    async def request_export(self, ctx: Context, since: str | None) -> str:
        raise NotImplementedError

    async def poll(self, ctx: Context, export_id: str) -> dict[str, Any]:
        """``{"status": "pending"|"ready"|"failed"|"expired", "chunks": [...], "retry_after": s}``"""
        raise NotImplementedError

    async def read_chunk(self, ctx: Context, export_id: str, chunk: Any) -> list[RawItem]:
        raise NotImplementedError


class Connector:
    """Base class. Subclasses set ``manifest`` and ``streams`` and override hooks."""

    manifest: Manifest
    stream_classes: ClassVar[tuple[type[Stream], ...]] = ()

    def __init__(self) -> None:
        self._streams = {cls.name: cls(self) for cls in self.stream_classes}
        missing = set(self.manifest.stream_names) - set(self._streams)
        if missing:
            raise ConfigInvalid(
                f"{self.manifest.id}: streams without implementation: {sorted(missing)}"
            )

    @property
    def id(self) -> str:
        return self.manifest.id

    def stream(self, name: str) -> Stream:
        try:
            return self._streams[name]
        except KeyError:
            raise ConfigInvalid(f"{self.manifest.id} has no stream {name!r}") from None

    def base_url(self, config: dict[str, Any], vendor_app: dict[str, Any] | None) -> str:
        """The API base URL for a connection (CAT-08 regions, GHES hosts)."""
        if self.manifest.regions:
            return self.manifest.regions[0].api_base
        raise ConfigInvalid("connector declares no region")

    def local_transport(self, config: dict[str, Any], options: dict[str, Any]) -> Any:
        """An in-process vendor (SANDBOX) returns an ``httpx2.AsyncBaseTransport`` here,
        so its requests never leave the process. Real connectors return None."""
        return None

    def package_dir(self) -> Any:
        """The connector's directory (manifest, fixtures, golden output)."""
        import importlib
        from pathlib import Path

        module = importlib.import_module(type(self).__module__)
        return Path(module.__file__ or ".").parent

    def auth_plan(
        self,
        *,
        credentials: dict[str, Any],
        vendor_secrets: dict[str, Any],
        vendor_config: dict[str, Any],
        config: dict[str, Any],
        http: Any,
    ) -> AuthPlan:
        """How this connection authenticates. The default covers the standard modes
        from the manifest: OAUTH2 (refresh token kept sealed, access tokens minted
        under the shared refresh discipline), OAUTH2_CC (client credentials), and the
        credential's ``api_key`` as a bearer token (API_KEY) or basic auth (BASIC)."""
        from securefabric_cdk import oauth2
        from securefabric_cdk.errors import ConfigInvalid
        from securefabric_cdk.tokens import StaticSecret
        from securefabric_schema import AuthMode

        auth = self.manifest.auth
        if auth.mode in (AuthMode.OAUTH2, AuthMode.OAUTH2_CC):
            cfg = auth.oauth2
            if cfg is None:
                raise ConfigInvalid(f"{self.manifest.id} declares {auth.mode} without oauth2")
            # The client: the customer's own (credentials) or the vendor app registration.
            client_id = credentials.get("client_id") or vendor_config.get("client_id")
            client_secret = credentials.get("client_secret") or vendor_secrets.get("client_secret")
            clock = getattr(http, "clock", None)
            now = clock.now if clock is not None else None
            if not client_id:
                raise ConfigInvalid("no OAuth client id: register the vendor app")
            if auth.mode is AuthMode.OAUTH2_CC:
                if not client_secret:
                    raise ConfigInvalid("client credentials need a client secret")
                exchange = oauth2.client_credentials_exchange(
                    http,
                    cfg.token_url,
                    client_id=str(client_id),
                    client_secret=str(client_secret),
                    scopes=cfg.scopes,
                    clock=now,
                )
            else:
                exchange = oauth2.refresh_exchange(
                    http,
                    cfg.token_url,
                    client_id=str(client_id),
                    client_secret=str(client_secret) if client_secret else None,
                    refresh_token=credentials.get("refresh_token"),
                    clock=now,
                )
            return AuthPlan(
                exchanges={"default": exchange},
                margins_s={"default": auth.token_refresh_margin_s},
            )
        if "api_key" in credentials:
            return AuthPlan(
                static_headers=StaticSecret.api_key(str(credentials["api_key"]))._headers
            )
        if "username" in credentials:
            return AuthPlan(
                static_headers=StaticSecret.basic(
                    str(credentials["username"]), str(credentials.get("password", ""))
                )._headers
            )
        return AuthPlan(static_headers={})

    def auth_scheme_for(self, purpose: str) -> str:
        """Which auth scheme the HTTP client should use for a purpose."""
        return "default"

    def platform_app(self) -> dict[str, Any] | None:
        """A vendor app the platform registers for every environment at bootstrap
        (``securefabric-admin bootstrap``): ``{"name", "base_url", "config",
        "secrets"}``. Most connectors return None and their apps come from settings
        or from customers; SANDBOX_OAUTH ships its synthetic OAuth client this way."""
        return None

    async def verify(self, ctx: Context) -> VerifyResult:
        raise NotImplementedError

    async def probe(self, ctx: Context, stream: str) -> Grant:
        return Grant(GrantStatus.GRANTED)

    def handle_webhook(
        self, delivery: IngressDelivery, *, config: dict[str, Any], options: dict[str, Any]
    ) -> list[WebhookEffect]:
        return []

    async def perform(self, ctx: Context, action: Action) -> ActionResult:
        raise NotImplementedError(f"{self.manifest.id} declares no actions")

    def sweep_confirmed(
        self, stream: str, *, would_delete: int, live: int, vendor_total: int | None
    ) -> bool:
        """A vendor-confirmed exception to the sweep guard (STORE-06). GitHub: the
        installation's repository count really did shrink."""
        return False
