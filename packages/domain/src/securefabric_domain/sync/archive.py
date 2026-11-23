"""The raw page archive (STORE-10, RAW-02, STORE-11).

Each successful vendor response is archived *before* it is parsed, so a
normaliser crash still leaves the evidence and re-normalisation can replay it.
Bytes are sealed to the environment key, stored in object storage with a 7-day
lifecycle rule, and indexed in ``sync.raw_page`` in their own short transaction.
"""

import json
from datetime import timedelta
from typing import Any
from uuid import UUID

from securefabric_core import get_logger
from securefabric_core.crypto import seal_envelope
from securefabric_core.ids import uuid7
from securefabric_db import fetch_one, tenant_tx
from securefabric_domain.runtime import Platform

RAW_RETENTION = timedelta(days=7)
log = get_logger(__name__)


class RawArchive:
    def __init__(
        self,
        platform: Platform,
        *,
        environment_id: UUID,
        connection_id: UUID,
        stream: str,
        stream_run_id: UUID | None,
        public_key: bytes,
        enabled: bool = True,
    ) -> None:
        self._p = platform
        self._env = environment_id
        self._conn_id = connection_id
        self._stream = stream
        self._run = stream_run_id
        self._public = public_key
        self._enabled = enabled
        self.seq = 0
        self.failures = 0
        self.last_id: UUID | None = None

    async def capture(self, *, request_summary: dict[str, Any], body: bytes) -> str | None:
        if not self._enabled:
            return None
        self.seq += 1
        page_id = uuid7()
        sealed = seal_envelope(
            self._public,
            environment_id=str(self._env),
            connection_id=str(self._conn_id),
            purpose="raw_page",
            payload={"summary": request_summary, "body": body.decode("utf-8", "replace")},
        )
        key = f"{self._env}/{self._conn_id}/{self._stream}/{page_id}"
        try:
            await self._p.blob.put(key, sealed)
        except Exception as exc:
            # The archive is evidence, not the source of truth: an object-store outage
            # (or clock skew) must not stop syncs. Record it and carry on.
            self.failures += 1
            log.warning("raw_archive_failed", error=type(exc).__name__, stream=self._stream)
            if self.failures == 1:
                from securefabric_domain.sync.scheduler import raise_alert

                async with self._p.pool.connection() as conn:
                    await raise_alert(
                        conn,
                        "raw_archive_failing",
                        str(self._conn_id),
                        {"error": f"{type(exc).__name__}: {str(exc)[:200]}"},
                        severity="ticket",
                    )
            return None
        now = self._p.clock.now()
        async with tenant_tx(self._p.pool, self._env) as conn:
            await conn.execute(
                """insert into sync.raw_page (id, environment_id, connection_id, stream, stream_run_id, seq, blob_key,
                                              bytes, request_summary, created_at, expires_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s)""",
                (
                    page_id,
                    self._env,
                    self._conn_id,
                    self._stream,
                    self._run,
                    self.seq,
                    key,
                    len(body),
                    json.dumps(request_summary, default=str),
                    now + RAW_RETENTION,
                ),
            )
        self.last_id = page_id
        return str(page_id)


async def read_raw_page(
    platform: Platform, environment_id: UUID, raw_page_id: UUID
) -> dict[str, Any] | None:
    """Worker-only: open an archived page (re-normalisation, the operator viewer)."""
    from securefabric_domain.vault import open_for

    async with tenant_tx(platform.pool, environment_id) as conn:
        row = await fetch_one(conn, "select * from sync.raw_page where id = %s", (raw_page_id,))
        if row is None:
            return None
        sealed = await platform.blob.get(row["blob_key"])
        if sealed is None:
            return None
        version = (
            await fetch_one(
                conn,
                "select vault_key_version from control.environment where id = %s",
                (environment_id,),
            )
            or {}
        ).get("vault_key_version", 1)
        payload: dict[str, Any] = await open_for(
            platform,
            conn,
            environment_id,
            sealed,
            version=version,
            connection_id=row["connection_id"],
            purpose="raw_page",
        )
    return {**row, **payload}
