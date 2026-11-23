# outbox_lag

**Severity:** page · **Subject:** none

## What it means

The oldest undispatched `events.outbox_event` row is more than 2 minutes old. Webhooks and the
`/v1/events` feed are behind. Resolves itself when the lag clears.

## Diagnose

1. The dispatcher runs inside the scheduler tick: is a scheduler online?
2. ```sql
   select count(*), min(created_at) from events.outbox_event where dispatched_at is null;
   ```
3. Delivery queue depth: `GET /v1/status` → queue `delivery`.

## Fix

Start a scheduler / delivery worker. Dispatch is idempotent per event × endpoint, so a backlog
drains without duplicates.

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
