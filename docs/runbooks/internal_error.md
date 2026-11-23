# internal_error

**Severity:** page · **Subject:** a stream run id, or `verify:<connection_id>`

## What it means

Code raised something that is not a classified vendor error: a bug. For a stream run, the
slice was retried once and then FAILED with `INTERNAL_ERROR`. For `verify:<id>`, a credential
verification failed all its Absurd attempts; the connection shows `INTERNAL_ERROR` (owner
PLATFORM) and, for a creation, `connection.create.failed` was emitted.

## Diagnose

- Run: `select error from sync.stream_run where id = '<run id>'` (redacted).
- Verification: the traceback is on the Absurd run, never copied elsewhere (it can carry
  anything):
  ```sql
  select r.attempt, r.failure_reason
    from absurd.r_control r join absurd.t_control t using (task_id)
   where t.task_name = 'connection.verify' and t.params->>'connection_id' = '<id>'
   order by r.attempt;
  ```

## Fix

Fix and release. Then: runs retry on their next schedule (or `trigger`); a connection stuck in
creation recovers when anyone tests it (`GET /v1/connections/{id}/test` retries creation for a
PENDING connection).

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
