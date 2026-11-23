"""Connector developer tools against a live connection (CDK-05, CDK-06).

``dryrun`` reads a few pages of one stream through the real HTTP client, normalises
them and reports what came out, persisting nothing: no records, no checkpoints, no
raw pages. ``record`` does the same through a recording transport and writes the
scrubbed responses to the connector's ``fixtures/`` directory, refusing to write a
file the secret scan flags.

They live in the admin CLI rather than ``securefabric-cdk`` because opening a
connection's credentials needs the vault and the database, which the CDK must not
depend on. The one side effect is the token cache: a refreshed OAuth token is saved
as in any sync, because a single-use refresh token must never be spent unrecorded.
"""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from securefabric_cdk.cli import check_capabilities, stream_capabilities
from securefabric_cdk.connector import ExportStream
from securefabric_cdk.fixtures import RecordingTransport, find_secrets, save_fixture
from securefabric_cdk.http import MemoryOpLog, NullBudget
from securefabric_cdk.types import NormalizeContext, Skip
from securefabric_core import NotFoundError, ValidationFailedError
from securefabric_db import fetch_one, system_tx, tenant_tx
from securefabric_domain.records import Invalid
from securefabric_domain.runtime import Platform
from securefabric_domain.sync.bundle import Bundle, build_context, load_bundle
from securefabric_schema import Mode


async def _bundle(platform: Platform, connection_id: UUID) -> tuple[UUID, Bundle]:
    async with system_tx(platform.sys_pool) as conn:
        row = await fetch_one(
            conn, "select environment_id from control.connection where id = %s", (connection_id,)
        )
    if row is None:
        raise NotFoundError("Connection not found", code="connection_not_found")
    env: UUID = row["environment_id"]
    async with tenant_tx(platform.pool, env) as conn:
        return env, await load_bundle(platform, conn, connection_id)


async def _read(
    platform: Platform,
    connection_id: UUID,
    stream_name: str,
    *,
    pages: int,
    mode: Mode,
    recorder: RecordingTransport | None = None,
) -> dict[str, Any]:
    _env, bundle = await _bundle(platform, connection_id)
    if stream_name not in bundle.manifest.stream_names:
        raise ValidationFailedError(
            f"{bundle.manifest.id} has no stream {stream_name!r}",
            code="unknown_stream",
            errors=[{"field": "stream", "message": f"one of {bundle.manifest.stream_names}"}],
        )
    stream = bundle.connector.stream(stream_name)
    if isinstance(stream, ExportStream):
        raise ValidationFailedError(
            "export streams are not supported here: they request a vendor export",
            code="export_stream",
        )
    ctx = await build_context(
        platform,
        bundle,
        stream=stream_name,
        op_log=MemoryOpLog(),
        capture=None,  # persists nothing: no raw page archive
        clock=platform.clock,
        interactive=True,
        budget=NullBudget(),
        transport=recorder,
    )
    nctx = NormalizeContext(options=bundle.options, config=bundle.config, stream=stream_name)
    from securefabric_domain.sync.executor import _normalize

    dumps: list[dict[str, Any]] = []
    skipped = 0
    invalid: list[dict[str, Any]] = []
    read_pages = items = 0
    try:
        async for page in stream.read(ctx, None, mode):
            read_pages += 1
            for raw in page.items:
                items += 1
                out = _normalize(stream, raw, nctx)
                if isinstance(out, Skip):
                    skipped += 1
                elif isinstance(out, Invalid):
                    invalid.append({"natural_key": out.natural_key, "errors": out.errors})
                elif hasattr(out, "model_dump"):
                    dumps.append(out.model_dump(mode="json", exclude={"vendor_data"}))
            if read_pages >= pages:
                break
    finally:
        requests = ctx.http.vendor_requests
        await ctx.http.aclose()
    spec = bundle.manifest.stream(stream_name)
    caps = stream_capabilities(spec.object, dumps)
    return {
        "connector": bundle.manifest.id,
        "connection_id": str(connection_id),
        "stream": stream_name,
        "mode": mode.value,
        "pages": read_pages,
        "vendor_requests": requests,
        "items": items,
        "records": len(dumps),
        "skipped": skipped,
        "invalid": invalid[:20],
        "capabilities": caps,
        "manifest_problems": check_capabilities(bundle.manifest, {"streams": {stream_name: caps}}),
        "_dumps": dumps,
        "_bundle": bundle,
    }


async def dryrun(
    platform: Platform,
    connection_id: UUID,
    stream_name: str,
    *,
    pages: int = 3,
    mode: Mode = Mode.FULL,
    sample: int = 3,
) -> dict[str, Any]:
    """CDK-06: read, normalise, report. Nothing is written."""
    result = await _read(platform, connection_id, stream_name, pages=pages, mode=mode)
    result["sample"] = result.pop("_dumps")[:sample]
    result.pop("_bundle")
    return result


async def record(
    platform: Platform,
    connection_id: UUID,
    stream_name: str,
    *,
    pages: int = 3,
    mode: Mode = Mode.FULL,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """CDK-05: record a stream's responses (scrubbed) as the connector's fixtures."""
    _env, bundle = await _bundle(platform, connection_id)
    connector = bundle.connector
    inner = connector.local_transport(bundle.config, bundle.options) or platform.vendor_transport()
    recorder = RecordingTransport(inner, scrub_fields=bundle.manifest.scrub_fields)
    # Verify and probes first, through the same recorder: a sandbox connection replays
    # them when it is created (TEN-13).
    vctx = await build_context(
        platform,
        bundle,
        stream=None,
        op_log=MemoryOpLog(),
        capture=None,
        clock=platform.clock,
        interactive=True,
        budget=NullBudget(),
        transport=recorder,
    )
    try:
        verified = await connector.verify(vctx)
        vctx.config.update(verified.config_updates)
        for s in bundle.integration["enabled_streams"]:
            if s in bundle.manifest.stream_names:
                await connector.probe(vctx, s)
    finally:
        await vctx.http.aclose()
    result = await _read(
        platform, connection_id, stream_name, pages=pages, mode=mode, recorder=recorder
    )
    result.pop("_dumps")
    result.pop("_bundle")
    connection_config = {
        k: v
        for k, v in vctx.config.items()
        # environment-specific or transient: never part of a shared fixture set
        if k not in ("_revoked", "installation_choices", "vendor_app_id")
    }
    # Token exchanges are never fixtures (they would only hold redacted noise).
    interactions = [
        i
        for i in recorder.interactions
        if "access_tokens" not in i.path and "/oauth/" not in i.path
    ]
    payload = {"interactions": [i.to_json() for i in interactions]}
    hits = find_secrets(payload, bundle.manifest.scrub_fields or ("secret",))
    if hits:
        raise ValidationFailedError(
            "the recording still holds secret-like values; nothing was written",
            code="fixture_not_clean",
            errors=[{"field": h, "message": "secret-like"} for h in hits[:20]],
        )
    target = (out_dir or connector.package_dir() / "fixtures") / f"{stream_name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    save_fixture(target, interactions)
    if find_secrets(connection_config, bundle.manifest.scrub_fields or ("secret",)):
        raise ValidationFailedError(
            "the connection config holds secret-like values", code="fixture_not_clean"
        )
    (target.parent / "connection.json").write_text(
        json.dumps(connection_config, indent=2, sort_keys=True, default=str) + "\n"
    )
    result["fixture"] = str(target)
    result["interactions"] = len(interactions)
    result["bytes"] = len(json.dumps(payload))
    return result
