# Part 9: Operations, security and quality

## 1. Observability

### Three audiences

| Audience | Sees | Source |
|---|---|---|
| Customer | Their connections' health, freshness, jobs and operation logs | `obs.operation`, `obs.operation_event` through the API and dashboard |
| Operator | Everything a customer sees for any account, plus scheduler state and raw pages | The admin console |
| Engineer on call | Metrics, traces, structured logs, alerts | OpenTelemetry export |

### Metrics (OPS-03)

Emitted through OpenTelemetry, so the backend is a deployment choice.

- Per connector: vendor request latency, 429 and 5xx rates, requests per run, records per second, run duration p50 and p95, quarantine count.
- Scheduler: admission lag (oldest admissible run's age), queue depth by state and priority, parked runs, schedule lateness.
- Store: batch write latency, lock wait time, rows written per second.
- API: request rate, latency by route, error rate, rate-limit rejections.
- Events: outbox lag (oldest undispatched event), delivery success rate, dead deliveries.
- Vault: opens per minute by role. A sudden rise is a security signal.

### Alerts (OPS-02)

Each has a runbook, written in the same change that adds the alert.

| Alert | Condition |
|---|---|
| Freshness breach | A healthy connection's stream is older than its interval plus 1 hour (NFR-02) |
| Admission lag | Oldest admissible run older than 5 minutes |
| Connector failure rate | More than 20% of a connector's runs failing across tenants for 10 minutes (RATE-08) |
| Sweep aborted | Any sweep guard trip |
| Quarantine spike | Quarantined records above 1% of a run |
| Outbox lag | Oldest undispatched event older than 2 minutes |
| Dead deliveries growing | |
| Refresh failures | Token refresh failing for a connector across tenants |
| Internal error | Any run ending `INTERNAL_ERROR` |
| Ingress signature failures | A burst of rejected inbound webhooks for one app |

### Logging

Structured JSON through the existing structlog setup, with request id, environment id, connection id and run id bound in context. Redaction happens in the logging pipeline, by field name and by pattern, before a line is written (SEC-07). Connector code logs through `ctx.log`, which goes to the operation log, not to stdout.

## 2. Security controls

| Control | Where | Requirement |
|---|---|---|
| TLS 1.2 or later, HSTS | Edge | SEC-01 |
| Sealed credentials, private key on workers only | Part 3, section 5 | SEC-02, AUTH-09 |
| Key rotation by version | Part 3, section 5 | SEC-03 |
| Row-level security on every tenant table | Part 2, section 1 | SEC-05 |
| No customer code, allowlisted connector dependencies | Part 1, section 3 | SEC-06 |
| Redaction, log scanning in CI | Section 1 above, section 4 below | SEC-07 |
| Audit log, append-only, 1 year | Part 2, section 5 | SEC-08 |
| Read-only vendor permissions by default, write in a separate app | Part 6, section 2 | SEC-09 |
| Egress policy with DNS pinning, for vendors and webhooks | Part 4, section 6 | RATE-07, HOOK-08, AUTH-12 |
| Installation binding verified by GitHub, never by URL | Part 6, section 3 | (found during design) |
| Inbound webhook signatures mandatory, payloads never trusted as data | Part 6, section 8 | PD-11 |
| API keys hashed, shown once, scoped, region-bound | Part 3, section 3 | TEN-06, TEN-07 |
| Signed, opaque pagination cursors | Part 7, section 4 | |
| Secret values from secret scanning never stored | Part 6, section 6 | (found during design) |

**Database roles.** Four roles, least privilege each:

| Role | Used by | Rights |
|---|---|---|
| `sf_migrate` | Migration runner | Owns the schemas |
| `sf_api` | `api` | Read and write on tenant tables through RLS. No access to `vault_private_key_wrapped`. |
| `sf_worker` | Sync, control, delivery workers | Read and write through RLS, plus the wrapped private key column |
| `sf_system` | Scheduler, retention | `bypassrls`, for cross-tenant scheduling and cleanup only |

Column-level grants keep the wrapped private key away from the API role, so the trust boundary in part 1 is enforced by Postgres, not only by which process holds the KEK.

**Threats considered and where they are handled.**

- A tenant reads another tenant's data: RLS plus repository scoping, the 404 rule, the cross-environment test suite.
- A tenant binds another tenant's GitHub installation: the OAuth verification in part 6, section 3.
- A compromised API host: cannot open the vault. Can forge inbound webhooks only if it also has the ingress key, and forged webhooks only cause re-fetches.
- A malicious vendor base URL or webhook URL reaching internal services: the egress policy.
- A leaked database backup: credentials are sealed, and destroying an environment's key shreds its secrets.
- A connector bug writing bad data: canonical validation and quarantine, the sweep guard, the reconcile pass.
- Credential material in logs, fixtures or error messages: redaction, fixture scrubbing, CI scanning.

Own-platform scanning (SEC-10): the repository is connected to the platform's own GitHub connector as the first dogfood tenant, alongside ordinary dependency and container scanning in CI. A penetration test before general availability is outside this plan.

## 3. Retention and maintenance

One `maintenance` queue with scheduled tasks, each idempotent and audited (STORE-12).

| Data | Kept | Mechanism |
|---|---|---|
| Normalised data | While the connection exists, then 30 days | Purge task on `purge_after` |
| Soft-deleted records | 90 days | Daily delete by `deleted_at` |
| State history | 13 months | Drop monthly partitions |
| Raw pages | 7 days | Object-store lifecycle rule, plus dropping index partitions |
| Jobs and stream runs | 90 days | Daily delete |
| Operation logs | 30 days | Drop daily partitions |
| Inbound webhook deliveries | 7 days | Drop daily partitions |
| Outbox events and delivery attempts | 90 and 30 days | Drop partitions, daily delete |
| Audit events | 1 year | Drop monthly partitions |
| Quarantine | 30 days | Daily delete |
| Idempotency keys | 24 hours | Hourly delete |
| OAuth state, used connect sessions | 2 days | Daily delete |
| Absurd tasks | 30 days after completion | Absurd's own cleanup policy, already configured |

A partition manager task creates future partitions for every range-partitioned table a week ahead and alerts if it ever falls behind.

## 4. Test strategy

The platform's correctness claims are specific, so the tests are too.

| Layer | What | Where |
|---|---|---|
| Unit | Canonical encoder and hashing, cursor encoding, state transition tables, health roll-up, admission ordering, backoff schedule, manifest validation, redaction | Each package |
| Property | Hash is independent of key order and float formatting. Keyset paging returns every row exactly once under any sort. Admission never exceeds a cap. | `schema`, `domain` |
| Database integration | `apply_batch` semantics, RLS denial with no tenant setting, partial unique indexes, sweep and guard, purge | `domain`, against real Postgres as the repo's `conftest.py` already does |
| Connector | Fixture replay, golden output, the conformance suite (part 5, section 5) | `connectors` |
| Engine scenarios | Parking, retries, crash and resume, cancellation, timeouts, fairness, priorities, exports, using SANDBOX scenarios | `worker` |
| API contract | Every endpoint and every filter, the error shape, idempotency, rate limiting, Leen V2 example payloads validating against our schema | `api` |
| Isolation | For every endpoint, a key from environment A gets 404 for every id from environment B (TEN-02). Generated from the OpenAPI document, so a new endpoint is covered automatically. | `api` |
| Concurrency | Parallel writers and readers on one connection over a large update set, asserting no reader skips a change (CDC-01) | `domain` |
| Secret hygiene | Run a full sync with canary credentials and scan every log line, operation record, fixture, error body and webhook payload for them (AUTH-09, SEC-07) | End to end |
| End to end | Compose stack: create an organization, connect SANDBOX and a GitHub sandbox connection, sync, read through the API, receive a signed webhook, pause, resume, delete, purge | CI |
| Live | Nightly sync against the seeded GitHub organization with drift detection | Scheduled |
| Load | 1,000 connections, 100 million findings, 10 million resources synthetic. API p95, ingest throughput, admission lag (NFR-04, 05, 06) | Before launch |
| Dashboard | Component tests for the form renderer and tables, and a small browser suite for connect, sync, explore | `dash` |

**Time.** Everything that reads the clock takes it from an injectable source. Absurd already exposes `absurd.current_time()` for this in the database. Engine scenario tests advance time instead of sleeping, so a test of the 24-hour webhook retry schedule runs in milliseconds.

**CI gates added to the existing `make verify`.** Import-boundary lint for connectors, manifest schema validation, OpenAPI breaking-change diff, fixture secret scan, generated-capabilities check, migration lint (no destructive statement without an expand step already shipped).

## 5. Deployment

- **Images.** The existing Dockerfile already builds `api` and `worker`. The worker image runs every role by argument.
- **Local.** `compose.yaml` gains MinIO and the worker roles. `make dev` continues to start everything with hot reload. A `make seed` target creates a development account, an environment, a SANDBOX connection and an API key, replacing the mock seed.
- **Configuration.** Environment variables through the existing settings classes. New groups: `VAULT_` (key provider, KEK reference), `BLOB_` (endpoint, bucket), `WORKOS_`, `REGION`, `GITHUB_APP_` (bootstrap of the platform-owned app registration on first start).
- **Migrations.** Run as a one-shot job before a deploy, as compose does today. Expand and contract across releases, so old and new code overlap safely (NFR-09).
- **Rolling deploys.** Workers stop claiming on SIGTERM, finish the current page, save the checkpoint and exit, as the existing shutdown handling already begins to do. A run interrupted by a deploy resumes on another worker and does not consume an attempt.
- **Backups.** Point-in-time recovery on the database, with the restore drill written as a runbook (NFR-08). The object store holds only 7 days of re-fetchable raw pages and is not backed up.
- **Regions.** One cell, with `REGION` baked into key prefixes. Infrastructure as code for a second cell is outside this plan (PD-15).

## 6. Capacity model

A check that the design fits the year-one target (NFR-06): 1,000 connections, 100 million findings, 10 million resources.

- **Rows.** 100 million findings over 64 partitions is about 1.6 million per partition on average. Connections are not uniform, so the largest partitions will be several times that, which is still comfortable for b-tree indexes.
- **Scheduling.** 1,000 connections times 5 streams hourly is about 1.4 stream runs a second, far below the admission design point.
- **Writes.** A daily change rate of 2% is 2 million changed findings a day, about 23 a second on average. A worker writes 2,000 a second, so steady state is a small fraction of one worker and backfills dominate.
- **Reads.** A connection-scoped list is one index range scan on one partition.
- **The risk** is observational writes: a full reconcile pass touches every row to set `last_seen_at` and `seen_gen`. At 100 million rows weekly that is about 165 heap-only updates a second on average, which is fine, but it produces dead tuples that autovacuum must keep up with. Partition-level autovacuum settings and the benchmark gate in part 10 cover this.
