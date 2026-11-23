# admission_lag

**Severity:** page · **Subject:** none (queue lag) or `run <id>` (a run expired)

## What it means

Two triggers share the name:

- **No subject**: the oldest admissible run (QUEUED, PARKED or RETRY_WAIT with `not_before`
  in the past) has waited more than 5 minutes. Admission is behind.
- **`run <id>`**: a run sat QUEUED for over an hour and was EXPIRED with `EXECUTION_TIMEOUT`
  (`QUEUE_WAIT_TIMEOUT`, part 4 section 5). That connection's stream missed a cycle.

## Diagnose

1. Is a scheduler online? `make status` → Processes / roles.
2. Are the caps saturated? `GET /v1/admin/scheduler` shows running counts per scope.
   Defaults: 3 per connection, 50 per environment, 500 per connector, 64 per queue, 2000 global
   (`DEFAULT_CAPS`); overrides live in `sync.concurrency_limit`.
3. Are sync workers draining? `GET /v1/status` (queues: `pending`, `oldest_pending_seconds`).
   ADMITTED runs whose Absurd task vanished are re-queued automatically by `expire()`.

## Fix

- Start sync workers / raise `WORKER_CONCURRENCY`.
- A noisy tenant: lower its environment cap with a `sync.concurrency_limit` row
  (`scope_kind = 'environment'`); fairness already round-robins by `fair_key`.
- For an expired run: `trigger` repair on that connection once capacity is back.

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
