# partition_manager_behind

**Severity:** page · **Subject:** comma-separated table names

## What it means

Rows landed in a `*_default` partition of a range-partitioned log/history table, so the
partition for that period did not exist when they were written. Retention cannot drop a
default partition by date, so these rows would never expire.

## Fix

1. Run the partition job now: it creates partitions 62 days ahead
   (`maintenance.partitions`, scheduled hourly on the maintenance queue).
2. Move the stray rows: for each listed table, detach the default partition, create the
   missing range partitions with `public.sf_ensure_partitions`, re-insert the rows, re-attach.
3. Find why the job fell behind (maintenance worker down? `make status`).

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
