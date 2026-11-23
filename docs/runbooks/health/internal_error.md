# INTERNAL_ERROR

**Owner:** PLATFORM · **Status:** UNHEALTHY

Something failed inside SecureFabric. We are alerted automatically (operators:
[internal_error](../internal_error.md)) and nothing is needed from the customer. A connection
that never finished being created recovers when it is tested again
(`GET /v1/connections/{id}/test`); otherwise the next scheduled sync retries.
