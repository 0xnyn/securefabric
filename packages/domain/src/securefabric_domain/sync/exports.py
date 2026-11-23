"""Async vendor exports (SYNC-16; docs/plan/04-sync-engine.md, section 11).

The engine drives ``ExportStream``: request → poll → download chunks.

- The export id lives in the ``export`` checkpoint, so a new slice continues the
  same export instead of requesting another.
- While the vendor prepares the export the run **parks** (no worker is held);
  it is re-admitted after the vendor's suggested delay.
- Chunks download with bounded parallelism; each chunk is applied and recorded in
  the checkpoint in one transaction, so a worker killed mid-download resumes with
  exactly the chunks it had not finished.
- An export the vendor expired is detected and requested again.
- A full export is a complete listing: it sweeps (deletion), with the guard.
"""

import asyncio
from datetime import timedelta
from typing import Any

from securefabric_cdk.connector import ExportStream
from securefabric_cdk.errors import ExportExpired
from securefabric_cdk.types import NormalizeContext, Skip
from securefabric_db import tenant_tx
from securefabric_domain import records
from securefabric_domain.records import BatchContext
from securefabric_domain.runtime import Platform
from securefabric_domain.sync import checkpoints
from securefabric_schema import Mode

PARALLEL_CHUNKS = 4
DEFAULT_POLL_S = 30.0
MAX_IN_SLICE_POLLS = 3


class ExportWait(Exception):
    """The export is still being prepared: park the run for ``seconds``."""

    def __init__(self, seconds: float) -> None:
        super().__init__(f"export pending, retry in {seconds}s")
        self.seconds = seconds


async def run_export(
    platform: Platform,
    inp: Any,
    bundle: Any,
    ctx: Any,
    stream: ExportStream,
    bctx: BatchContext,
    outcome: Any,
    op_log: Any,
    archive: Any,
    on_run_update: Any,
    heartbeat: Any,
) -> None:
    from securefabric_domain.sync.executor import _normalize

    full = inp.mode in (Mode.FULL, Mode.BACKFILL)
    async with tenant_tx(platform.pool, inp.environment_id) as conn:
        state, version = await checkpoints.load(conn, inp.connection_id, inp.stream, "export")
        default, _ = await checkpoints.load(conn, inp.connection_id, inp.stream)
        if full and inp.generation is None:
            inp.generation = await records.new_generation(conn)
    outcome.generation = inp.generation
    watermark = (default or {}).get("cursor", {}).get("watermark") if default else None
    state = state or {}
    if state.get("generation") not in (None, inp.generation) and full:
        state = {}  # an older pass's export: start over (same rule as listing checkpoints)
    bctx = BatchContext(**{**bctx.__dict__, "generation": inp.generation or 0}) if full else bctx
    nctx = NormalizeContext(options=bundle.options, config=bundle.config, stream=inp.stream)

    async def save(new_state: dict[str, Any]) -> None:
        nonlocal version, state
        async with tenant_tx(platform.pool, inp.environment_id) as conn:
            version = await checkpoints.save(
                conn,
                inp.environment_id,
                inp.connection_id,
                inp.stream,
                new_state,
                version,
                "export",
            )
        state = new_state

    for _attempt in range(3):  # an expired export is requested again
        if not state.get("export_id"):
            requested_at = platform.clock.now().isoformat()
            export_id = await stream.request_export(ctx, None if full else watermark)
            await save(
                {
                    "export_id": export_id,
                    "requested_at": requested_at,
                    "generation": inp.generation,
                    "chunks": None,
                    "done": [],
                }
            )
            ctx.log.info("export requested", export_id=export_id)
        try:
            if state.get("chunks") is None:
                polls = 0
                while True:
                    ctx.check()
                    status = await stream.poll(ctx, state["export_id"])
                    s = status.get("status")
                    if s == "ready":
                        await save({**state, "chunks": list(status.get("chunks") or [])})
                        break
                    if s in ("expired", "failed"):
                        raise ExportExpired(f"export {state['export_id']} {s}")
                    polls += 1
                    wait = float(status.get("retry_after") or DEFAULT_POLL_S)
                    if polls >= MAX_IN_SLICE_POLLS or wait > 10:
                        raise ExportWait(wait)
                    await platform.sleep(wait)
            pending = [c for c in state["chunks"] if c not in state["done"]]
            sem = asyncio.Semaphore(PARALLEL_CHUNKS)

            async def fetch(
                chunk: Any, sem: asyncio.Semaphore = sem, export_id: str = state["export_id"]
            ) -> tuple[Any, list[Any]]:
                async with sem:
                    return chunk, await stream.read_chunk(ctx, export_id, chunk)

            for i in range(0, len(pending), PARALLEL_CHUNKS):
                batch = await asyncio.gather(*(fetch(c) for c in pending[i : i + PARALLEL_CHUNKS]))
                for chunk, raw_items in batch:  # apply in chunk order, one transaction per chunk
                    ctx.check()
                    items = [
                        n
                        for n in (_normalize(stream, r, nctx) for r in raw_items)
                        if not isinstance(n, Skip)
                    ]
                    new_state = {**state, "done": [*state["done"], chunk]}
                    async with tenant_tx(platform.pool, inp.environment_id) as conn:
                        result = await records.apply_batch(
                            conn, bctx, items, raw_page_id=archive.last_id
                        )
                        version = await checkpoints.save(
                            conn,
                            inp.environment_id,
                            inp.connection_id,
                            inp.stream,
                            new_state,
                            version,
                            "export",
                        )
                        if on_run_update is not None:
                            await on_run_update(conn, result, ctx.http.vendor_requests)
                    state = new_state
                    outcome.counts.add(result)
                    outcome.pages += 1
                    if heartbeat is not None:
                        await heartbeat()
                    if inp.max_pages is not None and outcome.pages >= inp.max_pages:
                        from securefabric_domain.sync.executor import _Killed

                        raise _Killed()
            break
        except ExportExpired:
            ctx.log.warning(
                "export expired at the vendor; requesting a new one",
                export_id=state.get("export_id"),
            )
            await save({})
            continue
    else:
        raise ExportExpired("the vendor expired the export three times")

    async with tenant_tx(platform.pool, inp.environment_id) as conn:
        if full and inp.generation:
            would, live = await records.sweep_preview(conn, bctx, inp.generation)
            confirmed = bundle.connector.sweep_confirmed(
                inp.stream, would_delete=would, live=live, vendor_total=None
            )
            outcome.sweep = await records.sweep(conn, bctx, inp.generation, confirmed=confirmed)
            if outcome.sweep.aborted:
                s = outcome.sweep
                outcome.warning = (
                    f"sweep aborted: {s.would_delete} of {s.live} rows would be deleted"
                )
            else:
                outcome.counts.deleted += outcome.sweep.deleted
        await checkpoints.save(
            conn, inp.environment_id, inp.connection_id, inp.stream, {}, version, "export"
        )
        _, dv = await checkpoints.load(conn, inp.connection_id, inp.stream)
        await checkpoints.save(
            conn,
            inp.environment_id,
            inp.connection_id,
            inp.stream,
            {"cursor": {"watermark": state.get("requested_at")}, "pass": None},
            dv,
        )


def park_delay(exc: ExportWait) -> timedelta:
    return timedelta(seconds=exc.seconds)
