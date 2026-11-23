"""Vault service (docs/plan/03-tenancy-connections-vault.md, section 5).

- **Seal on arrival** (API): credentials are sealed to the environment public key
  before the request handler returns; plaintext is dropped.
- **Bind on open** (workers): the envelope's environment, connection and purpose
  must match the row it was read from (SEC-02).
- **Rotation** (SEC-03): environments carry a key version; sealed rows record the
  version they were sealed under; both versions open during re-sealing.
- **Platform key pair**: seals secrets of platform-owned vendor apps.
"""

import time
from typing import Any
from uuid import UUID

from securefabric_core.crypto import (
    VaultError,
    generate_key_pair,
    open_envelope,
    seal_envelope,
)
from securefabric_core.telemetry import instruments
from securefabric_db import Conn, fetch_one
from securefabric_domain.runtime import Platform

_PRIVATE_CACHE_TTL_S = 300.0
_private_cache: dict[tuple[str, int], tuple[float, bytes]] = {}


async def environment_public_key(conn: Conn, environment_id: UUID) -> tuple[bytes, int]:
    row = await fetch_one(
        conn,
        "select vault_public_key, vault_key_version from control.environment where id = %s",
        (environment_id,),
    )
    if row is None:
        raise VaultError("environment not found")
    return bytes(row["vault_public_key"]), int(row["vault_key_version"])


async def seal_for(
    conn: Conn, environment_id: UUID, *, connection_id: UUID | None, purpose: str, payload: Any
) -> tuple[bytes, int]:
    public, version = await environment_public_key(conn, environment_id)
    return seal_envelope(
        public,
        environment_id=str(environment_id),
        connection_id=str(connection_id) if connection_id else None,
        purpose=purpose,
        payload=payload,
    ), version


async def _environment_private_key(
    platform: Platform, conn: Conn, environment_id: UUID, version: int
) -> bytes:
    cache_key = (str(environment_id), version)
    hit = _private_cache.get(cache_key)
    if hit and time.monotonic() - hit[0] < _PRIVATE_CACHE_TTL_S:
        return hit[1]
    row = await fetch_one(
        conn,
        """select vault_key_version, vault_private_key_wrapped, vault_previous_private_key_wrapped
             from control.environment where id = %s""",
        (environment_id,),
    )
    if row is None:
        raise VaultError("environment not found")
    if version == row["vault_key_version"]:
        wrapped = row["vault_private_key_wrapped"]
    elif version == row["vault_key_version"] - 1 and row["vault_previous_private_key_wrapped"]:
        wrapped = row["vault_previous_private_key_wrapped"]
    else:
        raise VaultError(f"no key for vault version {version}")
    if wrapped is None:
        raise VaultError("the environment's key has been destroyed")
    private = platform.unwrap(bytes(wrapped))
    _private_cache[cache_key] = (time.monotonic(), private)
    return private


async def open_for(
    platform: Platform,
    conn: Conn,
    environment_id: UUID,
    sealed: bytes,
    *,
    version: int,
    connection_id: UUID | None,
    purpose: str,
) -> Any:
    """Worker-only. Raises VaultError on any binding mismatch."""
    instruments().vault_opens.add(1, {"role": platform.role, "purpose": purpose})
    private = await _environment_private_key(platform, conn, environment_id, version)
    return open_envelope(
        private,
        bytes(sealed),
        environment_id=str(environment_id),
        connection_id=str(connection_id) if connection_id else None,
        purpose=purpose,
    )


# ---------------------------------------------------------------- platform key pair


async def ensure_platform_key(platform: Platform, conn: Conn) -> bytes:
    row = await fetch_one(conn, "select public_key from control.platform_key where id = 1")
    if row:
        return bytes(row["public_key"])
    pair = generate_key_pair(platform.kek)
    await conn.execute(
        "insert into control.platform_key (id, public_key, private_key_wrapped) values (1, %s, %s)"
        " on conflict (id) do nothing",
        (pair.public_key, pair.private_key_wrapped),
    )
    row = await fetch_one(conn, "select public_key from control.platform_key where id = 1")
    assert row is not None
    return bytes(row["public_key"])


async def seal_platform(
    conn: Conn, platform: Platform, *, purpose: str, owner_id: str, payload: Any
) -> bytes:
    public = await ensure_platform_key(platform, conn)
    return seal_envelope(
        public, environment_id="platform", connection_id=owner_id, purpose=purpose, payload=payload
    )


async def open_platform(
    platform: Platform, conn: Conn, sealed: bytes, *, purpose: str, owner_id: str
) -> Any:
    row = await fetch_one(conn, "select private_key_wrapped from control.platform_key where id = 1")
    if row is None:
        raise VaultError("platform key not initialised")
    private = platform.unwrap(bytes(row["private_key_wrapped"]))
    return open_envelope(
        private, bytes(sealed), environment_id="platform", connection_id=owner_id, purpose=purpose
    )


# ---------------------------------------------------------------- vendor app secrets


async def open_vendor_app_secrets(
    platform: Platform, conn: Conn, app: dict[str, Any]
) -> dict[str, Any]:
    if not app.get("secrets_sealed"):
        return {}
    if app["environment_id"] is None:
        result: dict[str, Any] = await open_platform(
            platform, conn, app["secrets_sealed"], purpose="vendor_app", owner_id=str(app["id"])
        )
        return result
    opened: dict[str, Any] = await open_for(
        platform,
        conn,
        app["environment_id"],
        app["secrets_sealed"],
        version=app.get("secrets_key_version") or 1,
        connection_id=app["id"],
        purpose="vendor_app",
    )
    return opened


def clear_cache() -> None:
    _private_cache.clear()
