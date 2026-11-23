# INITIALIZING

**Owner:** PLATFORM · **Status:** INITIALIZING

The connection is verified and ACTIVE, but its first sync has not completed yet. A backfill of
a large tenant can take a while. Follow it with `GET /v1/connections/{id}/jobs` (the INITIAL
job lists each stream's state). Nothing to do unless it lasts more than a few hours; then see
the job's stream runs for PARKED (rate limits) or RETRY_WAIT (vendor errors).
