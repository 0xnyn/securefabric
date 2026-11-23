# refresh_failures

**Severity:** page · **Subject:** none

## What it means

The daily token-refresh sweep failed for at least 3 connections and for at least as many as
succeeded. One customer's revoked token is normal; many at once points at a vendor token
endpoint outage or a broken platform App secret.

## Diagnose

1. Worker logs: `token_refresh_failed` lines (connection id, error type).
2. Platform App configuration: `securefabric-admin bootstrap` re-reads `GITHUB_APP_*` from the
   environment; check the private key and client secret were not rotated at the vendor.

## Fix

Rotate/restore the platform App credentials and re-run `bootstrap`. Individual connections
whose refresh stays rejected for 4 separate days become `REAUTHORIZATION_REQUIRED` and need the
customer (see [health/reauthorization_required](health/reauthorization_required.md)).

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
