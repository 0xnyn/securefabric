# EXECUTION_TIMEOUT

**Owner:** PLATFORM · **Status:** UNHEALTHY

A run exceeded its deadline (4 hours by default) or waited in the queue for over an hour
without being admitted. Progress is checkpointed, so the next run continues where this one
stopped. Repeated timeouts on a very large tenant: operators can split work by raising the
connection's concurrency cap or lengthening the deadline; queue waits mean admission was
behind (see [admission_lag](../admission_lag.md)).
