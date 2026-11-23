# sweep_aborted

**Severity:** page · **Subject:** `<connection_id>/<stream>`

## What it means

A full pass finished and would have marked more than 50% (and more than 20 rows) of the
stream's live rows deleted. The sweep guard refused (part 2, deletion). Rows stay live; the run
ends with a warning. Typical causes: the vendor returned a truncated listing, a permission was
narrowed, or the customer really did delete most of it.

## Diagnose

1. `detail` holds `would_delete` and `live`.
2. Look at the run's operation log: `GET /v1/jobs/{job_id}/logs` (page counts, last cursor).
3. Raw pages of that pass: `GET /v1/admin/environments/{env}/raw_pages?connectionId=<id>`.
4. Ask the customer (or check the vendor UI) whether the objects are really gone.

## Fix

- Truncated listing / transient vendor issue: nothing; the next full pass re-evaluates.
- Real mass deletion: the connector's `sweep_confirmed` exception applies when the vendor
  reports a matching total; otherwise run `reset` with `{"wipe": true}` on the connection
  (operator repair) so the next backfill rebuilds from scratch.

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
