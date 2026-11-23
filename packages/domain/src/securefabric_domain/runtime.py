"""The platform runtime: one object holding what every service needs.

Each process builds one :class:`Platform` for its role. The role decides which
database role its pool uses and whether it may unwrap vault keys:

=========== ============ ===================== ==========================
role        db role      key provider          notes
=========== ============ ===================== ==========================
api         sf_api       wrap-only             cannot open the vault
scheduler   sf_system    none                  cross-tenant, bypassrls
sync        sf_worker    full (unwrap)         runs connector streams
control     sf_worker    full (unwrap)         verify, refresh, actions
delivery    sf_worker    full (unwrap)         webhook signing secrets
=========== ============ ===================== ==========================
"""

import asyncio
import base64
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

import httpx2

from securefabric_cdk.egress import EgressTransport
from securefabric_core.clock import SYSTEM_CLOCK, Clock
from securefabric_core.crypto import (
    IngressCipher,
    KeyProvider,
    LocalKeyProvider,
    PayloadKeyring,
    VaultError,
    WrapOnlyKeyProvider,
    decode_key,
)
from securefabric_core.platform import PlatformSettings, get_platform_settings
from securefabric_db import AsyncPool, DatabaseSettings, create_pool
from securefabric_domain.blob import BlobStore, MemoryBlobStore, S3BlobStore
from securefabric_domain.registry import ConnectorRegistry, default_registry

type Role = Literal["api", "scheduler", "sync", "control", "delivery", "maintenance", "test"]

_DB_ROLE = {
    "api": "sf_api",
    "scheduler": "sf_system",
    "maintenance": "sf_system",
    "sync": "sf_worker",
    "control": "sf_worker",
    "delivery": "sf_worker",
    "test": "sf_worker",
}


@dataclass
class Platform:
    settings: PlatformSettings
    role: Role
    pool: AsyncPool
    system_pool: AsyncPool | None
    kek: KeyProvider
    ingress: IngressCipher | None
    pepper: bytes
    cursor_key: bytes
    registry: ConnectorRegistry
    blob: BlobStore
    clock: Clock = SYSTEM_CLOCK
    # Builds the transport vendor calls go through. Tests swap in a replay transport.
    vendor_transport: Callable[[], httpx2.AsyncBaseTransport] = field(
        default=lambda: EgressTransport(httpx2.AsyncHTTPTransport(retries=0))
    )
    # Builds the transport outbound customer webhooks go through.
    webhook_transport: Callable[[], httpx2.AsyncBaseTransport] = field(
        default=lambda: EgressTransport(httpx2.AsyncHTTPTransport(retries=0))
    )
    database_url: str = ""
    region: str = "us"
    payload: PayloadKeyring | None = None  # STORE-09 vendor payload encryption
    # Injectable so retry and backoff tests run in milliseconds.
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep

    @property
    def can_unwrap(self) -> bool:
        return isinstance(self.kek, LocalKeyProvider)

    def unwrap(self, wrapped: bytes) -> bytes:
        if not self.can_unwrap:
            raise VaultError(f"role {self.role!r} cannot open the vault")
        return self.kek.unwrap(wrapped)

    async def open(self) -> None:
        await self.pool.open(wait=False)
        if self.system_pool is not None and self.system_pool is not self.pool:
            await self.system_pool.open(wait=False)

    async def close(self) -> None:
        await self.pool.close()
        if self.system_pool is not None and self.system_pool is not self.pool:
            await self.system_pool.close()

    @property
    def sys_pool(self) -> AsyncPool:
        if self.system_pool is None:
            raise RuntimeError(f"role {self.role!r} has no cross-tenant pool")
        return self.system_pool


def _secret(value: object | None, name: str) -> str:
    if value is None:
        raise VaultError(f"{name} is not configured")
    return str(value.get_secret_value()) if hasattr(value, "get_secret_value") else str(value)


def build_kek(settings: PlatformSettings, *, can_unwrap: bool) -> KeyProvider:
    if settings.vault_key_provider != "local":
        raise VaultError(f"unknown VAULT_KEY_PROVIDER {settings.vault_key_provider!r}")
    if can_unwrap:
        return LocalKeyProvider.from_b64(_secret(settings.vault_master_key, "VAULT_MASTER_KEY"))
    if settings.vault_kek_public_key:
        return WrapOnlyKeyProvider(
            decode_key(settings.vault_kek_public_key, name="VAULT_KEK_PUBLIC_KEY")
        )
    # Local development: derive the public half, keep nothing that can unwrap.
    return LocalKeyProvider.from_b64(
        _secret(settings.vault_master_key, "VAULT_MASTER_KEY")
    ).wrap_only()


def build_platform(
    role: Role,
    *,
    settings: PlatformSettings | None = None,
    db: DatabaseSettings | None = None,
    clock: Clock = SYSTEM_CLOCK,
    registry: ConnectorRegistry | None = None,
    blob: BlobStore | None = None,
    with_system_pool: bool | None = None,
) -> Platform:
    settings = settings or get_platform_settings()
    db = db or DatabaseSettings()
    db_role = _DB_ROLE[role]
    pool = create_pool(db, role=db_role, name=role)  # type: ignore[arg-type]
    wants_system = (
        with_system_pool
        if with_system_pool is not None
        else role in ("control", "sync", "delivery", "test", "scheduler", "maintenance")
    )
    system_pool = (
        pool
        if db_role == "sf_system"
        else (
            create_pool(db, role="sf_system", name=f"{role}-system", min_size=0, max_size=4)
            if wants_system
            else None
        )
    )
    can_unwrap = role in ("sync", "control", "delivery", "test", "maintenance")
    # Only roles that write or decode stored records hold the payload keys.
    payload = (
        PayloadKeyring.from_setting(_secret(settings.payload_keys, "PAYLOAD_KEYS"))
        if settings.payload_keys and role in ("sync", "control", "maintenance", "test")
        else None
    )
    ingress = (
        IngressCipher.from_b64(_secret(settings.ingress_key, "INGRESS_KEY"))
        if settings.ingress_key
        else None
    )
    if blob is None:
        if settings.blob_endpoint and settings.blob_access_key and settings.blob_secret_key:
            blob = S3BlobStore(
                endpoint=settings.blob_endpoint,
                bucket=settings.blob_bucket,
                access_key=_secret(settings.blob_access_key, "BLOB_ACCESS_KEY"),
                secret_key=_secret(settings.blob_secret_key, "BLOB_SECRET_KEY"),
                region=settings.blob_region,
            )
        else:
            blob = MemoryBlobStore()
    allow_private = settings.egress_allow_private
    return Platform(
        settings=settings,
        role=role,
        pool=pool,
        system_pool=system_pool,
        kek=build_kek(settings, can_unwrap=can_unwrap),
        ingress=ingress,
        payload=payload,
        pepper=_key_bytes(settings.api_key_pepper, "API_KEY_PEPPER"),
        cursor_key=_key_bytes(settings.cursor_signing_key, "CURSOR_SIGNING_KEY"),
        registry=registry or default_registry(),
        blob=blob,
        clock=clock,
        vendor_transport=lambda: EgressTransport(
            httpx2.AsyncHTTPTransport(retries=0), allow_private=allow_private
        ),
        webhook_transport=lambda: EgressTransport(
            httpx2.AsyncHTTPTransport(retries=0), allow_private=allow_private
        ),
        database_url=db.url,
        region=settings.region,
    )


def _key_bytes(value: object | None, name: str) -> bytes:
    raw = _secret(value, name)
    try:
        return decode_key(raw, name=name)
    except VaultError:
        # Accept any sufficiently long secret string, hashed to 32 bytes.
        if len(raw) < 32:
            raise
        import hashlib

        return hashlib.sha256(raw.encode()).digest()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()
