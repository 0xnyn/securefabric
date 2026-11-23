# UNAUTHORIZED

**Owner:** CUSTOMER · **Status:** UNHEALTHY

The vendor rejected the credentials (401), or a permission a stream needs is missing (403);
`streams[].grant` names the stream and the endpoint that was refused. Data synced so far stays
readable. Also raised when a GitHub App installation is suspended or uninstalled (schedules
pause until it is restored).

**Fix (customer):**
- Missing permission: grant it at the vendor (GitHub: accept the App's updated permissions or
  enable the feature, e.g. Dependabot alerts), then `GET /v1/connections/{id}/test`.
- Rejected credential: rotate it (`PATCH /v1/connections/{id}` with `credentials`; the new value
  is verified before it replaces the old one) or re-authorise through a connect session created
  with `connection_id`.
