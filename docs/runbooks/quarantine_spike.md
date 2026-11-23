# quarantine_spike

**Severity:** ticket · **Subject:** `<connection_id>/<stream>`

## What it means

More than 1% of a run's records failed canonical validation and went to `data.quarantine`
instead of the record tables. Usually a vendor shape change the connector's normaliser does not
handle.

## Diagnose

```sql
select errors::text as errors, count(*) from data.quarantine
 where connection_id = '<id>' and stream = '<stream>'
 group by 1 order by 2 desc limit 20;
```

Compare a quarantined payload with the connector's fixtures and golden output.

## Fix

Fix the connector mapping, add the new shape as a fixture, re-record golden output
(`securefabric-cdk`), release, then `renormalize` (operator repair) to replay the raw archive
through the new code with zero vendor calls (STORE-11).

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
