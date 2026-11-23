# raw_archive_failing

**Severity:** ticket · **Subject:** connection id (first failure per run)

## What it means

Writing a raw vendor page to the object store failed. The archive is evidence, not the source
of truth, so the sync carried on; those pages cannot be re-normalised or inspected later.

## Diagnose

`detail.error` holds the exception type and message from the object store. Common causes:
MinIO/S3 down, bad `BLOB_*` credentials, missing bucket, or clock skew
(`RequestTimeTooSkewed`, seen with Docker Desktop after sleep).

## Fix

Restore the object store (`make db-up` starts MinIO locally) or fix `BLOB_*`. For clock skew,
restart the Docker VM. New pages archive again immediately; missing ones come back with the
next full pass.

## Close it

Condition-based alerts (freshness, queue-lag admission, connector failure rate, outbox lag) resolve themselves on the next maintenance evaluation once the condition clears. Anything else: `POST /v1/admin/alerts/{id}/resolve` with `{"note": "what you did"}` (operators only; the note is kept in the alert's `detail.resolution`).
