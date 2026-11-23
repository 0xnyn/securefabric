# Part 4: Sync engine

The sync engine turns "this connection has these streams" into normalised rows, on time, within the vendor's limits, resumably, and without one tenant starving another. It is the part of the platform with the most ways to be subtly wrong, so this part is specific.

## 1. Vocabulary

- **Stream.** One data type from one connector, with its own schedule, checkpoint, status and counts (SYNC-02). GitHub has five: `repositories`, `branches`, `code_scanning_alerts`, `secret_scanning_alerts`, `dependabot_alerts`.
- **Schedule.** `sync.stream_schedule`: when a stream next runs.
- **Job.** The customer-visible record of streams started together for one connection.
- **Stream run.** One stream's execution within a job. The unit of admission, retry and health.
- **Slice.** One Absurd task executing part of a stream run. A run that parks for a rate limit and resumes later has several slices.
- **Mode.** `backfill` (first run, bounded by the lookback option), `incremental` (changes since the checkpoint), `full` (a complete pass, which may sweep), `targeted` (specific records named by webhooks).

## 2. Why two layers

Absurd claims runs in `available_at` order. It has no priority column, no fairness and no keyed concurrency. Those are requirements (SYNC-08, 11, 12), so they live one level up:

```
 sync.stream_run            the queue we control: priority, fairness, caps, backoff, parking
        │  admission (scheduler, once a second and on NOTIFY)
        ▼
 Absurd queues              only work that is allowed to run now
   sync_interactive         on-demand, initial, webhook-targeted
   sync_bulk                scheduled incrementals and full passes
        │  claim (workers)
        ▼
 sync worker                one slice of one stream run
```

Absurd contributes what is hard to get right: leases with claim timeouts, crash detection, cancellation, idempotent spawn. We contribute policy. A run that is queued, backing off or parked is just a row that has not been admitted, so nothing sits in Absurd waiting, and FIFO there is harmless.

Two Absurd queues with separate worker pools give a hard reservation: bulk work can never occupy the interactive workers, so an on-demand job starts promptly even when the bulk queue is saturated.

## 3. The scheduler loop

One active scheduler (leader-elected by advisory lock) runs these steps every second. Each step is one short transaction.

1. **Fire schedules.** Select schedules with `state = 'STARTED' and next_run_at <= now()` for active connections, `for update skip locked`. Group by connection. For each connection create one `job` and one `stream_run` per due stream, then advance `next_run_at` by the interval with ±10% jitter so connections created together drift apart. The partial unique index makes a duplicate insert a no-op: if a stream still has an active run, the schedule is advanced and nothing is queued.
2. **Admit.** Section 4.
3. **Expire.** Runs `QUEUED` for more than 1 hour become `EXPIRED` and raise an alert (queue-wait timeout). Runs past `deadline_at` are cancelled (run timeout). Runs in `RUNNING` whose Absurd task has failed its claim timeout are handled by Absurd, which re-queues the task for another worker (heartbeat timeout). These are the three timeouts of SYNC-09.
4. **Roll up jobs.** A job whose runs are all terminal gets its final status and, in the same transaction, its `sync.completed` outbox event and the connection's recomputed health.
5. **Dispatch outbox.** Part 7, section 9.

On-demand requests and inbound webhooks do `NOTIFY` after commit so admission runs immediately instead of on the next tick. This is the pattern Nango's orchestrator uses for its long-poll wake-up.

## 4. Admission: priority, fairness, concurrency

Candidates are runs in `QUEUED`, `PARKED` or `RETRY_WAIT` with `not_before <= now()`.

**Order.** By `priority`, then by fairness, then by age. Fairness is round-robin across `fair_key` (environment and organization): within a priority level, take the oldest run of each fair key in turn, least-recently-admitted key first. A tenant that queues 500 runs gets one slot per round like everyone else (SYNC-11).

**Caps.** A candidate is admitted only if all of these have room, counting runs in `ADMITTED` or `RUNNING`:

| Scope | Default | Purpose |
|---|---|---|
| Per budget key (vendor credential) | From the manifest. GitHub: 4. | Protects the vendor tenant and our rate budget |
| Per connection | 3 | Bounds database write contention for one connection |
| Per environment | 50 | Fairness between customers |
| Per connector | 500 | Blast radius if one vendor misbehaves |
| Per queue | Worker capacity × 2 | Keeps Absurd's backlog shallow |

Overrides live in `sync.concurrency_limit` (SYNC-12).

**Admit.** Spawn an Absurd task on the right queue with idempotency key `run:<run_id>:<attempt>:<slice>` and set the run to `ADMITTED`. Because counting and admitting happen in one transaction under the scheduler's leader lock, caps cannot be oversubscribed by a race.

`PARKED` runs do not count against any cap. A run waiting 20 minutes for GitHub's rate limit to reset holds no worker and no slot (RATE-02).

## 5. Executing a slice

```
handler(stream_run_id):
    run   = load and mark RUNNING (first slice sets started_at)
    conn  = load connection, integration, connector (pinned version)
    auth  = TokenProvider.get()                       # vault opened here, worker only
    ckpt  = load checkpoint(connection, stream)
    stream = connector.stream(run.stream)

    async for page in stream.read(ctx, ckpt, run.mode):       # connector code
        archive raw page                                      # object store, before parsing
        records = [stream.normalize(raw) for raw in page.items]
        valid, invalid = validate(records)                    # canonical schema
        with tenant_tx:                                       # ONE transaction per page
            lock (connection, object_type)
            upsert valid, write links, state history, quarantine invalid
            update stream_head (counts, clock)
            save checkpoint (version check)
            add to run counters
        heartbeat (extend the Absurd claim)
        if cancel requested or deadline passed: stop cleanly

    if mode is full and the pass completed: sweep (section 8)
    mark SUCCEEDED, advance schedule.last_success_at
```

Points that matter:

- **The page is the unit of durability.** Records, checkpoint, counts and state history for a page commit together or not at all. A worker killed at any instant leaves the store exactly at a page boundary, and the next slice resumes from the saved checkpoint (SYNC-04). There is no "wrote the records but lost the checkpoint" state.
- **Absurd steps are not used for pages.** Absurd memoises step results by name to replay them. A stream with thousands of pages would accumulate thousands of memoised results. Our own checkpoint table is the resume mechanism for stream loops. Absurd steps are used where they fit: short multi-step workflows such as connection verification and webhook delivery.
- **Raw before parse.** The page is archived before normalisation, so a normaliser crash still leaves the evidence, and re-normalisation (STORE-11) can replay it.
- **Heartbeat.** The claim timeout is 5 minutes and is extended after every page and at least once a minute during long waits.
- **Cancellation** (SYNC-13). The handler runs a small watcher that reads `cancel_requested` once a second. On cancel it cancels the in-flight fetch, lets the current page transaction finish or roll back, and exits with the last committed checkpoint, inside the 5-second target.

### Outcomes

The CDK raises a small, closed set of errors. The handler maps each to what happens next.

| Outcome | Run state | Next |
|---|---|---|
| Completed | `SUCCEEDED` | Schedule advances |
| Vendor asked us to wait more than 2 minutes | `PARKED`, `not_before` = reset time | Re-admitted after the reset, same attempt |
| Retryable failure (5xx, network, timeout) | `RETRY_WAIT`, `not_before` = now + backoff | Attempts at 1, 5, 15 and 60 minutes, with ±20% jitter, then `FAILED` until the next scheduled slot (SYNC-10) |
| Auth rejected | `FAILED`, `UNAUTHORIZED` | No retry. Health changes. |
| Configuration or unclassified 4xx | `FAILED` | No retry |
| Deadline passed | `FAILED`, `EXECUTION_TIMEOUT` | Checkpoint kept, next scheduled run continues from it |
| Cancelled | `CANCELLED` | Checkpoint kept |
| Worker died | Absurd re-queues the task | Next slice resumes from the checkpoint. Does not consume an attempt. |
| Bug (unexpected exception) | `RETRY_WAIT` once, then `FAILED`, `INTERNAL_ERROR` | Pages on-call |

Waits of 2 minutes or less are slept in-process, because releasing and re-admitting costs more than it saves.

## 6. Vendor API hygiene

All of this lives in the CDK's HTTP client, so no connector implements it.

**Declared retry policy** (RATE-01). The manifest names retryable statuses, the header carrying a reset time, the header carrying a retry-after, the header carrying remaining quota, and optional body patterns. GitHub needs the body pattern: a secondary rate limit is a 403 whose body says so, and it must not be mistaken for a permission error.

**Shared rate budget** (RATE-03). One `sync.rate_bucket` row per budget key. For GitHub the key is the installation, because GitHub's limit is per installation and several streams, several workers and possibly several of our connections share it.

- Workers do not take a database lock per request. A worker leases a block of tokens (say 50) in one `update`, spends them locally, and returns the unused ones.
- After each response the client reports the vendor's own `remaining` and `reset` headers, and the bucket is corrected to the lower of our count and the vendor's. The vendor's header is the truth, and our bucket is a prediction that keeps us from needing it.
- A second bucket per key caps requests per minute for GitHub's secondary limit (900 points a minute, where a read costs 1 and a write costs 5). We target at most 10 requests a second per installation.

**Proactive throttling** (RATE-04). Below 10% remaining, scheduled work pauses and only interactive work continues, so an on-demand job or a webhook refresh still has budget.

**Parking** (RATE-02). A wait longer than 2 minutes parks the run.

**401 handling** (RATE-05). One retry, only if the token provider returned a different token after a forced refresh. Otherwise the run fails as `UNAUTHORIZED`.

**Timeouts and network errors** (RATE-06). Connect timeout 10 seconds, idle read timeout 5 minutes, retries with backoff on reset, timeout, refused and DNS failure.

**Egress** (RATE-07, AUTH-12). The client resolves the host, checks every resolved address against the deny list (private, loopback, link-local, metadata), connects to the checked address, and re-checks on each redirect, capped at 3. Customer-supplied base URLs (GHES) are validated at connection create time and again on every request, which closes DNS rebinding.

**Pagination** (RATE-09). Helpers for link-header, cursor, page-token and offset pagination. Each yields pages together with an opaque resume token for the checkpoint.

**Outage detection** (RATE-08, P1). A rolling error rate per connector across tenants. Crossing the threshold raises an internal incident and marks affected connections `VENDOR_SERVER_ERROR` with owner `VENDOR`, instead of blaming each customer.

## 7. The write path

One function, `records.apply_batch(connection, stream, records, generation)`, is the only way rows enter `data.*`. For a batch of at most 1,000 records in one transaction:

1. `pg_advisory_xact_lock(hash(connection_id, object_type))` (STORE-13). All writers for one connection and object type are serialised.
2. Read `stream_head.head_updated_at`. Compute `ts = greatest(clock_timestamp(), head_updated_at + 1 microsecond)`.
3. Ensure referenced resources exist. A finding that names a resource we have not seen gets a stub resource row (`is_stub = true`) with the right id, so no finding ever points at nothing (NORM-14). The owning stream fills it in later.
4. One `insert ... on conflict (connection_id, natural_key) do update` that:
   - always sets `last_seen_at` and `seen_gen`,
   - sets the canonical columns, `hash` and `updated_at = ts` only `where hash is distinct from excluded.hash`,
   - clears `deleted_at` if the row was deleted (undelete, STORE-04),
   - returns, per row, whether it was inserted, changed, undeleted or unchanged.
5. For rows whose normalised `state` changed, append to `state_history`, and set `state_updated_at` to the vendor's timestamp when the connector marks it trustworthy, otherwise to `ts` (NORM-05).
6. Replace `finding_resource` links for changed findings.
7. Update `stream_head`: counts, bytes, `head_updated_at = ts`.
8. Save the checkpoint.

### Why `updated_at` is assigned this way (PD-6)

A reader paging by `updated_at` can miss rows if a transaction with an earlier timestamp commits after the reader has passed that point. Nango orders by `(updated_at, id)` with no guard against this. Here, every writer for a connection and object type holds the same lock from before it picks `ts` until it commits, and `ts` is strictly greater than the last committed head. So timestamps are assigned in commit order, and `(updated_at, id)` is a cursor that cannot skip (CDC-01).

Organization-wide feeds merge several connections whose locks are independent, so those queries hide rows younger than 5 seconds, which is longer than any batch transaction is allowed to run (a statement timeout enforces it).

### State rules the platform applies

Connectors report the vendor's current state. The platform derives the rest, so every connector behaves the same way:

- A row that was `CLOSED` or `IGNORED` and is now reported open becomes `REOPENED`, not `OPEN`.
- A row that was deleted and reappears becomes `OPEN`, or `REOPENED` if it was `CLOSED` before deletion (STORE-04).
- `REOPENED` stays until the vendor reports a non-open state.
- `severity_floor` filtering happens here, after normalisation, so the natural key and state history stay consistent if the option changes.

## 8. Deletion detection

Each stream declares one mode in its manifest (STORE-05).

**`vendor_reported`.** The vendor tells us about closures and removals through the normal feed. Nothing extra happens during incremental runs.

**`sweep`.** Records not seen in a complete pass are deleted.

1. A full pass takes a `generation` from a sequence when it starts and stores it on the run and in the `sweep` checkpoint. A retry or resumed slice reuses it.
2. Every row observed gets `seen_gen = generation`.
3. Only after the stream's `read()` returns normally, meaning the vendor's listing was fully consumed, the sweep runs: `update ... set deleted_at, state = 'DELETED' where connection_id = $1 and stream = $2 and deleted_at is null and seen_gen < $generation`, in batches, with state history.
4. **Guard** (STORE-06). Before sweeping, count what would be deleted. If it is more than 50% of the stream's live rows (and more than 20 rows), abort the sweep, leave the data alone, mark the run `SUCCEEDED` with a warning, and page on-call. A connector can declare a vendor-confirmed exception (for GitHub: the installation's repository list really did shrink, confirmed by the installation's own repository count).

An interrupted pass never sweeps, and a resumed pass keeps its generation, so resuming deletes exactly what an uninterrupted pass would have (STORE-05's acceptance test).

**`none`.** Declared in capabilities, and the API says so.

**Reconcile passes.** An incremental stream with `vendor_reported` deletion still does a periodic full pass (`full_every_s`, default 7 days) with a sweep. This catches whatever the incremental feed cannot express, such as records that vanished because their parent was deleted, and it bounds the damage of any incremental bug to one reconcile interval.

**Cascade.** When a resource is deleted, findings whose primary resource it was are deleted in the same sweep. For GitHub this handles a repository removed from the installation.

## 9. On-demand, reset and re-normalise

- **On-demand job** (SYNC-06). `POST /v1/connections/{id}/jobs` with optional `streams`, `force_full_refresh`, `since`. If a stream already has an active run, that run's job is returned instead of creating another, so two quick POSTs return the same job id. An active scheduled run is promoted to priority 0.
- **Reset** (SYNC-14). Clears checkpoints and queues a full pass. Because writes are hash-compared, a reset on an unchanged tenant reports zero added and zero updated. An optional `wipe` deletes the connection's rows first, for corrupted data, and is restricted to admins.
- **Re-normalise** (STORE-11). A maintenance task replays archived raw pages through the current normaliser with no vendor calls. Limited to the 7-day archive window.

## 10. Targeted refresh

Inbound webhooks insert into `sync.dirty_record`. The scheduler, seeing dirty rows for a connection, creates a `targeted` run at priority 0. The worker drains up to 200 dirty keys, calls the stream's `read_one(key)` for each, and writes through the same `apply_batch`. Targeted runs are exempt from the one-active-run index, because they are small and do not touch checkpoints.

If more than 500 keys are dirty for one stream, the scheduler drops them and triggers an ordinary incremental run instead, which is cheaper than hundreds of single fetches.

## 11. Async vendor exports

GitHub does not need this, but Tenable, Qualys and Defender do (SYNC-16), so it is a CDK primitive built and tested against SANDBOX.

```
ExportStream:
    request_export(ctx, since)  -> export_id          # checkpointed
    poll(ctx, export_id)        -> pending | ready(chunks) | failed
    read_chunk(ctx, export_id, chunk) -> page
```

The engine saves the export id in the `export` checkpoint, polls with backoff by parking the run between polls (so no worker is held while the vendor prepares the export), downloads chunks with bounded parallelism, and records each completed chunk in the checkpoint. A worker killed mid-download resumes with the chunks it has not finished. An export the vendor has expired is detected and requested again.

## 12. Service levels the engine is built to

| Target | Mechanism |
|---|---|
| 99% of scheduled runs start within 15 minutes of due time (NFR-02) | One-second scheduler tick, shallow Absurd backlog, an alert on admission lag |
| An on-demand job starts within 60 seconds under load | Reserved interactive queue, priority 0, fairness |
| A dead worker's run resumes within 6 minutes | 5-minute claim timeout |
| A webhook-reported change is visible within 2 minutes (SYNC-19) | Targeted refresh at priority 0 |
| 2,000 records a second per worker (NFR-05) | Batched upsert, one transaction per page, no per-row round trips |
