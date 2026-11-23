# freshness_breach

**Severity:** ticket · **Subject:** `<connection_id>/<stream>` · **Raised by:** `maintenance.alerts` (every minute)

## What it means

A HEALTHY, ACTIVE connection has a STARTED stream whose last successful sync is older than
its interval plus one hour (NFR-02). Data is still served, but it is getting stale while the
connection reports itself healthy, so something is stopping runs from being scheduled or admitted.

## Diagnose

1. `GET /v1/admin/scheduler`: is the stream's run QUEUED, PARKED or RETRY_WAIT, and since when?
2. ```sql
   select state, not_before, attempt, health_code, error, created_at
     from sync.stream_run where connection_id = '<id>' and stream = '<stream>'
    order by created_at desc limit 5;
   ```
3. No recent run at all: check `sync.stream_schedule` (`state`, `next_run_at`) and that a
   scheduler is online (`make status` → Processes; `GET /v1/status` with a key).
4. Runs QUEUED for long: see [admission_lag](admission_lag.md) (caps, workers).
5. Runs PARKED repeatedly: the vendor's rate limit cannot fit the interval; consider a longer
   stream interval for that integration.

## Fix

- Scheduler down: start a worker with the `scheduler` role (or `all`).
- Stuck run: `POST /v1/admin/environments/{env}/connections/{id}/trigger` (operator repair,
  `X-Support-Reason` header) to queue a fresh run.

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
