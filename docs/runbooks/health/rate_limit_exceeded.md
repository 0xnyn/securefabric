# RATE_LIMIT_EXCEEDED

**Owner:** VENDOR · **Status:** UNHEALTHY

Vendor rate limits stopped a sync from finishing in time. Waits longer than 2 minutes park the
run (no worker is held) until the vendor's reset; this code means it kept happening. Usually
clears by itself. If it persists, the stream interval is too short for the tenant's size or
other tools share the same vendor quota; lengthen the integration's stream interval.
