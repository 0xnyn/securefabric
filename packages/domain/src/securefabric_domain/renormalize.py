"""Re-normalisation from the raw page archive (STORE-11).

Replays archived vendor responses (7-day window) through the current
normaliser, with no vendor calls, and writes through the normal path. Writes are
hash-compared, so only records whose mapping output changed move.
"""

import json
from typing import Any
from uuid import UUID

from securefabric_cdk.types import NormalizeContext, Skip
from securefabric_db import fetch_all, tenant_tx
from securefabric_domain import records
from securefabric_domain.records import BatchContext
from securefabric_domain.runtime import Platform
from securefabric_domain.sync.archive import read_raw_page

ITEM_KEYS = ("items", "repositories", "data", "results")


def items_of(body: Any) -> list[Any] | None:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in ITEM_KEYS:
            if isinstance(body.get(k), list):
                return list(body[k])
        if "id" in body or "number" in body:
            return [body]
    return None


async def renormalize(
    platform: Platform, environment_id: UUID, connection_id: UUID, stream: str
) -> dict[str, Any]:
    from securefabric_domain.sync.bundle import load_bundle
    from securefabric_domain.sync.executor import _normalize

    async with tenant_tx(platform.pool, environment_id) as conn:
        bundle = await load_bundle(platform, conn, connection_id)
        pages = await fetch_all(
            conn,
            """select id from sync.raw_page where connection_id = %s and stream = %s
                                          and expires_at > %s order by created_at, seq""",
            (connection_id, stream, platform.clock.now()),
        )
    s = bundle.connector.stream(stream)
    spec = bundle.manifest.stream(stream)
    nctx = NormalizeContext(options=bundle.options, config=bundle.config, stream=stream)
    bctx = BatchContext(
        environment_id,
        bundle.connection["organization_id"],
        connection_id,
        stream,
        spec.object,
        bundle.manifest.version,
        payload_cipher=platform.payload,
    )
    total = records.BatchResult()
    replayed = 0
    for p in pages:
        raw = await read_raw_page(platform, environment_id, p["id"])
        if raw is None:
            continue
        try:
            body = json.loads(raw["body"])
        except ValueError:
            continue
        items = items_of(body)
        if not items:
            continue
        normalized = [n for n in (_normalize(s, i, nctx) for i in items) if not isinstance(n, Skip)]
        async with tenant_tx(platform.pool, environment_id) as conn:
            total.add(await records.apply_batch(conn, bctx, normalized, raw_page_id=p["id"]))
        replayed += 1
    return {
        "pages": replayed,
        "updated": total.updated,
        "unchanged": total.unchanged,
        "added": total.added,
        "quarantined": total.quarantined,
    }
