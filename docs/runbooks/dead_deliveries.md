# dead_deliveries

**Severity:** ticket · **Subject:** `endpoint <id> disabled`

## What it means

A customer's webhook endpoint failed every delivery for 5 days and was disabled
(`disabled_reason = 'failing continuously for 5 days'`). Events keep accumulating in the
outbox and the `/v1/events` pull feed; nothing is lost.

## Fix

Tell the customer (their environment id is in `detail`). Once their receiver works they
re-enable the endpoint (`PATCH /v1/webhook_endpoints/{id}` with `enabled: true`) and replay
what they missed (`POST /v1/webhook_endpoints/{id}/replay`, one event or a range).

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
