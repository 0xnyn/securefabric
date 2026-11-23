# VENDOR_CLIENT_ERROR

**Owner:** CUSTOMER · **Status:** UNHEALTHY

The vendor rejected a request with a 4xx other than auth or rate limiting (e.g. 404 for an
organisation that was renamed, 422 for an option the vendor no longer accepts). Not retried.
Check the connection's options and the vendor tenant; the run's error in
`GET /v1/jobs/{id}` names the request. Fix, then `POST /v1/connections/{id}/jobs`.
