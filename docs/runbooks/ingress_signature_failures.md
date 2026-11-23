# ingress_signature_failures

**Severity:** ticket · **Subject:** `<connector>/<vendor app>`

## What it means

At least 10 inbound webhooks for one vendor app failed signature verification within a
minute. Either the webhook secret changed at the vendor without us, or someone is probing the
ingress URL. Rejected deliveries are not stored and have no effect.

## Diagnose

1. Was the App's webhook secret rotated? Compare with `GITHUB_APP_WEBHOOK_SECRET` (platform
   app) or the customer's vendor app.
2. Source of the requests: API access logs for `/v1/ingress/...`.

## Fix

Secret drift: update it (platform: `.env` + `securefabric-admin bootstrap`; customer app:
`PATCH` the vendor app). Then let the redelivery poller (every 15 min) recover what failed;
GitHub never retries on its own. Probing: nothing to do, rejection is constant-time.

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
