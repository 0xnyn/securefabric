# connector_failure_rate

**Severity:** page · **Subject:** connector id (e.g. `GITHUB`)

## What it means

Over the last 10 minutes at least 10 runs of one connector finished and more than 20% FAILED
with `VENDOR_SERVER_ERROR` or `RATE_LIMIT_EXCEEDED` (RATE-08). Usually a vendor outage or a
platform-wide rate-limit problem, not one customer.

## Diagnose

1. Check the vendor's status page (GitHub: githubstatus.com).
2. ```sql
   select health_code, error->>'message' as msg, count(*)
     from sync.stream_run
    where connector_id = '<CONNECTOR>' and finished_at > now() - interval '30 minutes'
    group by 1, 2 order by 3 desc;
   ```
3. Rate limits across many tenants of one platform App: check the App's budget keys in
   `sync.rate_bucket` (GitHub limits per installation, so this is rare).

## Fix

Nothing to do for a vendor outage: runs retry at 1/5/15/60 minutes and parked runs resume at
the vendor's reset. Customer-visible health shows `VENDOR_SERVER_ERROR` (owner VENDOR). If our
requests are the cause (a bad release), roll back.

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
