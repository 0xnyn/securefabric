"""Executing one slice of one stream run (docs/plan/04-sync-engine.md, section 5).

The same function serves the Absurd slice handler (M3) and the in-process test
harness (M2), so what is tested is what runs.

- **The page is the unit of durability.** Records, checkpoint, counts and state
  history for a page commit together or not at all.
- **Raw before parse.** The HTTP client archives the page before normalisation.
- **Checkpoints are tied to a pass.** A full pass stores its generation with its
  position; a new pass never resumes an older pass's listing.
- **Sweep only after a complete listing**, behind the guard.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx2
from pydantic import ValidationError

from securefabric_cdk.connector import ExportStream, Stream
from securefabric_cdk.errors import (
    AuthRejected,
    Cancelled,
    ConfigInvalid,
    ConnectorError,
    CursorExpired,
    DeadlineExceeded,
    ExportExpired,
    FeatureNotEnabled,
    PermissionMissing,
    RateLimited,
    ReauthorizationRequired,
    VendorRejected,
    VendorUnavailable,
)
from securefabric_cdk.types import GoneMarker, NormalizeContext, Skip, Tombstone
from securefabric_core import get_logger
from securefabric_core.clock import Clock
from securefabric_core.redact import redact
from securefabric_db import fetch_one, tenant_tx
from securefabric_domain import records
from securefabric_domain.records import BatchContext, BatchResult, Invalid, SweepResult
from securefabric_domain.runtime import Platform
from securefabric_domain.sync import checkpoints
from securefabric_domain.sync.archive import RawArchive
from securefabric_domain.sync.bundle import Bundle, build_context, load_bundle
from securefabric_domain.sync.oplog import OperationLog
from securefabric_domain.sync.ratebudget import DbRateBudget
from securefabric_domain.vault import environment_public_key
from securefabric_schema import GrantStatus, HealthCode, Mode, Severity

log = get_logger(__name__)


@dataclass
class SliceInput:
    environment_id: UUID
    connection_id: UUID
    stream: str
    mode: Mode
    run_id: UUID | None = None
    generation: int | None = None
    deadline: datetime | None = None
    interactive: bool = False
    target_keys: list[str] | None = None
    max_pages: int | None = None  # tests: stop after N pages, as if the worker died


@dataclass
class SliceOutcome:
    kind: str  # completed | parked | retry | failed | cancelled | killed
    health_code: HealthCode = HealthCode.HEALTHY
    error: dict[str, Any] | None = None
    reset_at: datetime | None = None
    counts: BatchResult = field(default_factory=BatchResult)
    pages: int = 0
    vendor_requests: int = 0
    sweep: SweepResult | None = None
    warning: str | None = None
    grant: tuple[GrantStatus, str | None, str | None] | None = None
    generation: int | None = None
    vendor_total: int | None = None


CancelCheck = Callable[[], Awaitable[bool]]
Heartbeat = Callable[[], Awaitable[None]]


def _error(exc: BaseException) -> dict[str, Any]:
    detail = getattr(exc, "detail", None) or {}
    out: dict[str, Any] = redact({"type": type(exc).__name__, "message": str(exc)[:1000], **detail})
    return out


def classify(exc: BaseException) -> SliceOutcome:
    """Map the closed error set to an outcome (part 4, section 5)."""
    if isinstance(exc, Cancelled):
        return SliceOutcome("cancelled", HealthCode.HEALTHY)
    if isinstance(exc, DeadlineExceeded):
        return SliceOutcome("failed", HealthCode.EXECUTION_TIMEOUT, _error(exc))
    if isinstance(exc, FeatureNotEnabled):
        return SliceOutcome(
            "completed",
            HealthCode.HEALTHY,
            warning="feature_not_enabled",
            grant=(GrantStatus.NOT_ENABLED, exc.scope, exc.message),
        )
    if isinstance(exc, PermissionMissing):
        return SliceOutcome(
            "failed",
            HealthCode.UNAUTHORIZED,
            _error(exc),
            grant=(GrantStatus.UNAUTHORIZED, exc.endpoint, exc.message),
        )
    if isinstance(exc, ReauthorizationRequired):
        return SliceOutcome("failed", HealthCode.REAUTHORIZATION_REQUIRED, _error(exc))
    if isinstance(exc, AuthRejected):
        return SliceOutcome("failed", HealthCode.UNAUTHORIZED, _error(exc))
    if isinstance(exc, RateLimited):
        return SliceOutcome(
            "parked", HealthCode.RATE_LIMIT_EXCEEDED, _error(exc), reset_at=exc.reset_at
        )
    if isinstance(exc, (VendorUnavailable, httpx2.TransportError)):
        return SliceOutcome("retry", HealthCode.VENDOR_SERVER_ERROR, _error(exc))
    if isinstance(exc, VendorRejected):
        code = (
            HealthCode.UNAUTHORIZED if exc.status in (401, 403) else HealthCode.VENDOR_CLIENT_ERROR
        )
        return SliceOutcome("failed", code, _error(exc))
    if isinstance(exc, ConfigInvalid):
        return SliceOutcome("failed", HealthCode.CONFIGURATION_ERROR, _error(exc))
    if isinstance(exc, (checkpoints.CheckpointConflict, CursorExpired, ExportExpired)):
        return SliceOutcome("retry", HealthCode.INTERNAL_ERROR, _error(exc))
    if isinstance(exc, ConnectorError):
        return SliceOutcome("failed", exc.health_code, _error(exc))
    return SliceOutcome("bug", HealthCode.INTERNAL_ERROR, _error(exc))


def _normalize(stream: Stream, raw: dict[str, Any], nctx: NormalizeContext) -> Any:
    try:
        return stream.normalize(raw, nctx)
    except ValidationError as exc:
        return records.invalid_from(exc, _guess_key(raw))
    except Exception as exc:  # a normaliser bug quarantines the record, not the run
        return Invalid(
            natural_key=_guess_key(raw),
            errors=[{"type": "normalize_error", "msg": repr(exc)[:500]}],
        )


def _guess_key(raw: dict[str, Any]) -> str | None:
    for k in ("id", "number", "key"):
        if k in raw:
            return str(raw[k])
    return None


async def run_slice(
    platform: Platform,
    inp: SliceInput,
    *,
    op_log: OperationLog,
    clock: Clock | None = None,
    cancel_check: CancelCheck | None = None,
    heartbeat: Heartbeat | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
    on_run_update: Callable[[Any, BatchResult, int], Awaitable[None]] | None = None,
) -> SliceOutcome:
    clock = clock or platform.clock
    async with tenant_tx(platform.pool, inp.environment_id) as conn:
        bundle = await load_bundle(platform, conn, inp.connection_id)
        public, _ = await environment_public_key(conn, inp.environment_id)
    if bundle.connection["deleted_at"] is not None:
        return SliceOutcome("cancelled", HealthCode.HEALTHY, warning="connection deleted")
    if inp.stream not in bundle.manifest.stream_names:
        return SliceOutcome(
            "failed",
            HealthCode.CONFIGURATION_ERROR,
            {
                "type": "ConfigInvalid",
                "message": f"{bundle.manifest.id} has no stream {inp.stream!r}",
            },
        )
    spec = bundle.manifest.stream(inp.stream)
    archive = RawArchive(
        platform,
        environment_id=inp.environment_id,
        connection_id=inp.connection_id,
        stream=inp.stream,
        stream_run_id=inp.run_id,
        public_key=public,
    )
    budget = DbRateBudget(
        platform.pool,
        bundle.budget_key(),
        per_hour=bundle.manifest.http.budget.per_hour,
        per_second=bundle.manifest.http.budget.max_requests_per_second,
        clock=clock,
        sleep=platform.sleep,
    )
    ctx = await build_context(
        platform,
        bundle,
        stream=inp.stream,
        op_log=op_log,
        capture=archive,
        clock=clock,
        interactive=inp.interactive,
        deadline=inp.deadline,
        budget=budget,
        transport=transport,
    )
    stream = bundle.connector.stream(inp.stream)
    floor = bundle.options.get("severity_floor")
    bctx = BatchContext(
        environment_id=inp.environment_id,
        organization_id=bundle.connection["organization_id"],
        connection_id=inp.connection_id,
        stream=inp.stream,
        object_type=spec.object,
        connector_version=bundle.manifest.version,
        generation=0,
        stream_run_id=inp.run_id,
        severity_floor=Severity(floor) if floor else None,
        payload_cipher=platform.payload,
    )
    outcome = SliceOutcome("completed")
    watcher: asyncio.Task[None] | None = None
    try:
        if cancel_check is not None:
            watcher = asyncio.create_task(_watch_cancel(ctx, cancel_check))
        if inp.mode is Mode.TARGETED:
            await _run_targeted(
                platform, inp, bundle, ctx, stream, bctx, outcome, op_log, on_run_update
            )
        elif isinstance(stream, ExportStream):
            from securefabric_domain.sync.exports import run_export

            await run_export(
                platform,
                inp,
                bundle,
                ctx,
                stream,
                bctx,
                outcome,
                op_log,
                archive,
                on_run_update,
                heartbeat,
            )
        else:
            await _run_listing(
                platform,
                inp,
                bundle,
                ctx,
                stream,
                bctx,
                outcome,
                op_log,
                archive,
                on_run_update,
                heartbeat,
            )
    except Exception as exc:
        from securefabric_domain.sync.exports import ExportWait

        killed = isinstance(exc, _Killed)
        if isinstance(exc, ExportWait):
            failed = SliceOutcome(
                "parked",
                HealthCode.HEALTHY,
                reset_at=clock.now() + __import__("datetime").timedelta(seconds=exc.seconds),
            )
        else:
            failed = classify(exc) if not killed else SliceOutcome("killed")
        failed.counts, failed.pages, failed.generation = (
            outcome.counts,
            outcome.pages,
            outcome.generation,
        )
        if failed.kind == "bug":
            log.exception("slice_bug", stream=inp.stream, connection_id=str(inp.connection_id))
        if failed.kind not in ("killed",):
            op_log.log(
                "error" if failed.kind in ("failed", "bug") else "warning",
                f"{inp.stream}: {failed.kind} ({failed.health_code})",
                error=failed.error.get("message") if failed.error else None,
            )
        outcome = failed
    finally:
        if watcher is not None:
            watcher.cancel()
        outcome.vendor_requests = ctx.http.vendor_requests
        await budget.release()
        await ctx.http.aclose()
        await op_log.flush()
    return outcome


class _Killed(Exception):
    """Test hook: simulates the worker dying at a page boundary."""


async def _watch_cancel(ctx: Any, check: CancelCheck) -> None:
    while True:
        await asyncio.sleep(1.0)
        if await check():
            ctx.cancelled = True
            return


def _pass_info(inp: SliceInput) -> dict[str, Any]:
    return {"mode": inp.mode.value, "generation": inp.generation}


async def _run_listing(
    platform: Platform,
    inp: SliceInput,
    bundle: Bundle,
    ctx: Any,
    stream: Stream,
    bctx: BatchContext,
    outcome: SliceOutcome,
    op_log: OperationLog,
    archive: RawArchive,
    on_run_update: Callable[[Any, BatchResult, int], Awaitable[None]] | None,
    heartbeat: Heartbeat | None,
) -> None:
    full = inp.mode in (Mode.FULL, Mode.BACKFILL)
    sweeping = (
        full
        and stream.spec.deletion.value != "none"
        and not (inp.mode is Mode.BACKFILL and bundle.options.get("initial_lookback_days"))
    )
    async with tenant_tx(platform.pool, inp.environment_id) as conn:
        stored, version = await checkpoints.load(conn, inp.connection_id, inp.stream)
        if full and inp.generation is None:
            inp.generation = await records.new_generation(conn)
    outcome.generation = inp.generation
    stored = stored or {}
    same_pass = stored.get("pass") == _pass_info(inp)
    # A new full pass keeps only the persistent keys; a resumed pass keeps its position.
    resume = stored.get("cursor")
    cursor = stream.fresh_checkpoint(resume) if full and not same_pass else resume
    bctx = BatchContext(**{**bctx.__dict__, "generation": inp.generation or 0}) if full else bctx
    nctx = NormalizeContext(options=bundle.options, config=bundle.config, stream=inp.stream)
    pages = 0
    async for page in stream.read(ctx, cursor, inp.mode):
        ctx.check()
        normalized = [_normalize(stream, raw, nctx) for raw in page.items]
        items = [n for n in normalized if not isinstance(n, Skip)]
        new_cursor = page.checkpoint if page.checkpoint is not None else cursor
        async with tenant_tx(platform.pool, inp.environment_id) as conn:
            result = await records.apply_batch(conn, bctx, items, raw_page_id=archive.last_id)
            version = await checkpoints.save(
                conn,
                inp.environment_id,
                inp.connection_id,
                inp.stream,
                {"cursor": new_cursor, "pass": _pass_info(inp)},
                version,
            )
            if on_run_update is not None:
                await on_run_update(conn, result, ctx.http.vendor_requests)
        cursor = new_cursor
        outcome.counts.add(result)
        outcome.pages += 1
        pages += 1
        if page.vendor_total is not None:
            outcome.vendor_total = page.vendor_total
        await op_log.maybe_flush()
        if heartbeat is not None:
            await heartbeat()
        if inp.max_pages is not None and pages >= inp.max_pages:
            raise _Killed()

    # The listing was fully consumed.
    async with tenant_tx(platform.pool, inp.environment_id) as conn:
        if sweeping and inp.generation:
            would, live = await records.sweep_preview(conn, bctx, inp.generation)
            confirmed = bundle.connector.sweep_confirmed(
                inp.stream, would_delete=would, live=live, vendor_total=outcome.vendor_total
            )
            outcome.sweep = await records.sweep(conn, bctx, inp.generation, confirmed=confirmed)
            if outcome.sweep.aborted:
                outcome.warning = (
                    f"sweep aborted: {outcome.sweep.would_delete} of {outcome.sweep.live} rows "
                    "would be deleted (guard, STORE-06)"
                )
                op_log.log("warning", outcome.warning)
            else:
                outcome.counts.deleted += outcome.sweep.deleted
        # Close the pass: keep the cursor (it carries the watermark), forget the pass.
        await checkpoints.save(
            conn,
            inp.environment_id,
            inp.connection_id,
            inp.stream,
            {"cursor": cursor, "pass": None},
            version,
        )


async def _run_targeted(
    platform: Platform,
    inp: SliceInput,
    bundle: Bundle,
    ctx: Any,
    stream: Stream,
    bctx: BatchContext,
    outcome: SliceOutcome,
    op_log: OperationLog,
    on_run_update: Callable[[Any, BatchResult, int], Awaitable[None]] | None,
) -> None:
    """Webhook-named records, re-fetched from the vendor (PD-11, section 10)."""
    nctx = NormalizeContext(options=bundle.options, config=bundle.config, stream=inp.stream)
    items: list[Any] = []
    for key in inp.target_keys or []:
        ctx.check()
        raw = await stream.read_one(ctx, key)
        if isinstance(raw, GoneMarker):
            items.append(Tombstone(stream.spec.object, key))
            continue
        result = _normalize(stream, raw, nctx)
        if not isinstance(result, Skip):
            items.append(result)
    async with tenant_tx(platform.pool, inp.environment_id) as conn:
        batch = await records.apply_batch(conn, bctx, items)
        await conn.execute(
            "delete from sync.dirty_record where connection_id = %s and stream = %s and vendor_key = any(%s)",
            (inp.connection_id, inp.stream, inp.target_keys or []),
        )
        if on_run_update is not None:
            await on_run_update(conn, batch, ctx.http.vendor_requests)
    outcome.counts.add(batch)
    outcome.pages = 1


async def stream_counts(
    platform: Platform, environment_id: UUID, connection_id: UUID
) -> list[dict[str, Any]]:
    async with tenant_tx(platform.pool, environment_id) as conn:
        from securefabric_db import fetch_all

        return await fetch_all(
            conn,
            "select * from data.stream_head where connection_id = %s order by stream",
            (connection_id,),
        )


async def last_checkpoint(
    platform: Platform, environment_id: UUID, connection_id: UUID, stream: str
) -> Any:
    async with tenant_tx(platform.pool, environment_id) as conn:
        row = await fetch_one(
            conn,
            "select value from sync.checkpoint where connection_id = %s and stream = %s "
            "and key = 'default'",
            (connection_id, stream),
        )
    return row["value"] if row else None
