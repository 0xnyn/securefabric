# VENDOR_SERVER_ERROR

**Owner:** VENDOR · **Status:** UNHEALTHY

The vendor kept returning 5xx (or timing out) after retries at 1, 5, 15 and 60 minutes. Usually
a vendor incident; check its status page. The next scheduled run retries automatically and the
connection returns to HEALTHY on success. Operators see many of these at once as
[connector_failure_rate](../connector_failure_rate.md).
