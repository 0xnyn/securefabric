# CONFIGURATION_ERROR

**Owner:** CUSTOMER · **Status:** UNHEALTHY

The connection's options or base URL are invalid (an option the connector rejects, a base URL
that fails the egress policy, a stream the connector no longer has). Not retried. Correct the
options with `PATCH /v1/connections/{id}` (they are validated against the connector's schema),
then trigger a sync.
