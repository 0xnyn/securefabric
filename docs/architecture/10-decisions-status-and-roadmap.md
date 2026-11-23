# Part 10: Decisions, status and roadmap

This part steps back from mechanisms. It records the architectural decisions as they were actually built, where the build departed from the plan and why, what is proven and at what level of evidence, and what is not done yet. Read it before proposing a structural change, before a launch-readiness review, or when deciding what to build next.

## 1. Where the build stands

All eleven milestones of the plan (M0 to M10) are built, and each item in [`progress.md`](../../progress.md) is checked only with the evidence that validated it. The platform syncs a real GitHub organization end to end (install through our own link, six repositories, 61 alerts across all three families). A dismissal on GitHub shows up in SecureFabric in 5.7 s, the dashboard runs on the real API with WorkOS sign-in, and every benchmark gate that was run passed on a laptop.

"Built" is not the same as "launchable". The plan's own [definition of done](../plan/10-delivery-plan.md#9-definition-of-done) is the honest yardstick:

| # | Definition of done | Status | What is missing |
|---|---|---|---|
| 1 | GitHub passes conformance, nightly live sync green for two weeks, every part 6 item built or listed optional | **Partly** | Conformance passes (FakeGitHub and recorded fixtures), and live syncs were run by hand. There is no nightly live sync job, so the two-week record cannot exist yet. |
| 2 | SANDBOX passes conformance, including the primitives GitHub does not use | **Done** | |
| 3 | A new connector built by someone who did not write the CDK, with no change outside `packages/connectors/` | **Not done** | `test_tooling` proves a scaffolded connector passes verify, sync and conformance with no outside changes, but no second person has written a real connector. |
| 4 | Every requirement built or named in the plan's exclusions | **Done** | Exclusions are listed in the plan's traceability table and section 6 below. |
| 5 | The dashboard has no mock data | **Done** | The mock store, simulated traffic and `lib/catalog.ts` are deleted. |
| 6 | All benchmark gates pass | **Partly** | Ingest, data API at 1M findings, admission, outbox, scale-out and Absurd throughput pass. Measured on a laptop, not production hardware. The 1M-finding backfill gate and the 100M-row reconcile/autovacuum gate were not run. |
| 7 | Every spike closed | **Done, with fallbacks** | S2, S3, S4 and S11 are closed by adopting the plan's fallback rather than by a live answer. S3 in particular keeps alert streams on a daily full reconcile until `updated_at` behaviour is confirmed. |

The short version: the architecture is complete and validated in tests and against live GitHub. What is left is **production substrate** (a real KMS, deployment, a second region), **sustained live evidence** (nightly syncs, production-scale benchmarks), and **the scope the plan deliberately deferred**.

## 2. Decision log as built

The plan's decisions ([../plan/01-architecture.md, section 6](../plan/01-architecture.md#6-decision-log)) held up. The table records how each one landed and what would make us revisit it.

| # | Decision | As built | Evidence | Revisit if |
|---|---|---|---|---|
| PD-1 | Absurd for durable execution, our own admission layer above it | `sync.stream_run` holds every scheduling decision; the leader-elected scheduler admits by priority, fair-key round-robin and caps, and spawns into Absurd in the same transaction. Five queues. | `test_engine.py`: 500 queued runs of one tenant do not delay another tenant's on-demand run. Bench: 1,158 admitted runs/s (gate 200). Absurd: 46k-118k tasks/min. | Admission lag grows past 5 s at real load, or a single scheduler leader becomes a bottleneck (shard by environment hash). |
| PD-2 | Two reference connectors, GitHub and SANDBOX | Both built and held to the same 11-test conformance suite. SANDBOX also has `SANDBOX_OAUTH` and `SANDBOX_CC` variants. | `test_sandbox_conformance.py` (17 tests), `test_github.py` (27 tests), live GitHub sync. | The next real connector needs a primitive neither exercises. Then that primitive gets a SANDBOX scenario first. |
| PD-3 | Account → Environment → Organization → Connection, with Integration between connector and connection | As designed. Creating a connection with only a vendor resolves to the environment's default integration. | `test_connections.py`, `test_isolation.py`. | |
| PD-4 | Credentials sealed to a per-environment public key; only workers hold the private key | Built, with an asymmetric KEK (see deviation D-2), so the API can create environments without being able to unwrap. | `test_rls.py` (API role denied wrapped keys), `test_crypto.py`, restore drill opens a sealed credential from a restored copy. | A KMS provider is added (section 5). The interface is ready; the implementation is not. |
| PD-5 | Typed canonical tables, hash-partitioned by connection, `seen_gen` for sweeps | As designed, 64 hash partitions. | `test_records.py`, sweep guard tests, conformance test 9. | |
| PD-6 | Monotonic `updated_at` under the write lock | Built, with the clock in `data.object_clock` per (connection, object type) (deviation D-3). | CDC-01 concurrency test: 4 writers × 3 readers, zero skipped changes. | |
| PD-7 | Replace the mock schema and domain package | Done. `0002_control_plane.sql`, the mock domain and the dashboard mock layer are deleted. | Git history. | |
| PD-8 | One `/v1` API, two authenticators | Built. The dashboard calls the same API through a same-origin proxy. | `test_openapi.py`, dashboard tests, live sign-in. | |
| PD-9 | Wire-compatible with Leen V2, improvements additive | Built and tested against Leen's own published JSON Schema. Where Leen's real API differed from the plan's assumptions, the code follows Leen. | `test_data.py` contract tests, `test_a_leen_v2_client_works_after_the_migration_guide_changes`. | |
| PD-10 | Shared GitHub App by default, customer-owned supported | Built. Customer-owned apps have write-only secrets and an egress-checked base URL (needed for GHES). | `test_github.py` install flow, live install. | All github.com tenants depend on one app's standing with GitHub. Revisit if that becomes a business risk. |
| PD-11 | Webhooks never carry data into the store | Built. Ingress marks records dirty; a targeted refresh re-fetches them. | Dismiss on GitHub → IGNORED via re-fetch, live in 5.7 s. | |
| PD-12 | Vendor payloads stored as opaque bytes from day one | Built. Format `0x02` is AES-256-GCM with versioned keys (STORE-09), turned on without a migration, as intended. | `test_payload_key_rotation_drill`; 527 live payloads sealed. | |
| PD-13 | Retries are ours, crash recovery is Absurd's | Built. Classified failures end the task with an outcome; the run row waits for 1/5/15/60 min. | `test_engine.py` retry and worker-death tests. | |
| PD-14 | Logs and audit start in Postgres | Built: operations and lines in daily partitions, audit and usage monthly, behind small reader/writer functions. | `test_maintenance.py`, `test_operations_log_and_usage`. | Log volume makes Postgres the wrong store; the reader/writer interfaces are the seam. |
| PD-15 | One cell, region as configuration | Built: region is baked into API key prefixes and checked per request. Only one region exists. | `test_core.py::test_authentication_errors_are_problem_json` (a key with another region's prefix gets 401 `wrong_region`). | A second region is needed; that is deployment work (section 5). |

## 3. Deviations from the plan

Each deviation was made deliberately during the build, and each has a reason. They are also listed in `progress.md`.

| # | Plan said | Built instead | Why |
|---|---|---|---|
| D-1 | `sync.ingress_delivery` range-partitioned by day | Unpartitioned, with a daily retention delete | The `(vendor_app_id, delivery_id)` uniqueness that makes ingress idempotent must hold across days; a unique constraint cannot span range partitions keyed on time. |
| D-2 | A symmetric KEK | An asymmetric (X25519) KEK | The API must create environments, which means wrapping a new private key, but must never unwrap. With an asymmetric KEK the API holds only the public half. |
| D-3 | Monotonic clock on `stream_head` | `data.object_clock` per (connection, object type) | Two streams can write one object type (GitHub repositories and branches both write resources; SANDBOX findings and exports both write findings). The clock has to be per object type to keep `updated_at` commit-ordered. |
| D-4 | Leen facts as assumed in the plan | Leen facts as researched (`docs/research/leen-v2-and-workos.md`) | For example, Leen has no `X-ORGANIZATION-ID` header. Ours is additive. |
| D-5 | API role reads operational tables directly | Status, API-call flushing and the operator console go through `SECURITY DEFINER` functions: `obs.system_status()`, `obs.flush_api_calls()`, the `control.operator_*` functions | Found live: `GET /v1/status` reported `down` (`InsufficientPrivilege` as `sf_api`) and metering never flushed. **Caveat:** `progress.md` and the comments in 0006/0007 say this leaves `sf_api` with no direct rights on cross-tenant data. The grants in `0002_platform.sql` say otherwise: `sf_api` holds select/insert/update/delete on every table in `control`, `sync`, `data`, `events` and `obs` (only wrapped key columns are withheld and audit is append-only) and on the Absurd tables. The migration ledger `public.schema_migrations` is the one table it cannot read. See 5.1. |
| D-6 | No `payload_unreadable` alert | A `payload_unreadable` alert with a runbook | Rows sealed with a key that is no longer loaded are unrecoverable. The re-encryption job raises an alert instead of failing silently or stalling. |
| D-7 | `securefabric-cdk dryrun|record` | `securefabric-admin dryrun|record` | Opening a live connection's credential needs the vault and the database, which the CDK must not depend on. |
| D-8 | OAuth authorize URLs are vendor websites | Manifests may say `authorize_url: local:/path` | SANDBOX has no website. The platform serves that page through the connector's in-process vendor, and accepts only the connector's own callback as `redirect_uri`. |
| D-9 | `GET /v1/status` behind authentication | Readable without credentials, returning only the summary | Workers, queues and counts need a key or session; alert subjects (other tenants' ids) are operator-only. |
| D-10 | Verification crash leaves the connection PENDING | A crashed verification is retried by Absurd; on the final attempt the connection gets `INTERNAL_ERROR` (owner PLATFORM), `connection.create.failed` is emitted and an alert raised | Found during validation: a crash left connections PENDING forever with no signal. Exception text is never copied anywhere because it can carry credentials. |
| D-11 | Weekly reconcile for alert streams | Daily (`full_every: 86400`) | Spike S3 could not confirm that GitHub's `updated_at` moves on every change. Relax to weekly once it is verified live. |
| D-12 | Schedules copied at activation | The scheduler leader reconciles every schedule at start (`reconcile_all_schedules`) | Found live: connector releases never reached existing connections' schedules, and a shorter cadence would only apply after the old interval elapsed. |

## 4. What is proven, and how strongly

Evidence comes in four strengths. Knowing which one backs a claim tells you how much to trust it in production.

| Strength | What it means | Examples |
|---|---|---|
| **Test** | Automated, runs in CI on every push (Postgres in a container) | RLS isolation, cross-environment 404s, CDC ordering under concurrency, sweep guards, webhook signing and the four-language verification samples, retry schedules, parking, idempotency, OpenAPI typing, connector conformance and golden output, generated docs and client drift |
| **Live** | Run by hand against real external systems, recorded in `progress.md` | GitHub App install and binding, full sync of the seeded org, dismiss/reopen round trip (5.7 s / 3.6 s), write-back, redelivery poller against GitHub's delivery log, WorkOS sign-in → onboarding, OTLP export, OAuth flows over ngrok, NVD/KEV/EPSS/OSV enrichment |
| **Benchmark** | Measured by `tools/bench/*` on a developer laptop's Postgres | Ingest 2,919 findings/s, data API p95 ≤ 30 ms at 1M findings, admission 1,158 runs/s, outbox 100% within 60 s, 1.87× scale-out, Absurd 46k-118k tasks/min |
| **Drill** | A scripted operational exercise run once | Restore from backup (dump 1.2 s, restore 3.5 s, sealed credential opens), rolling deploy under load (386/386 × 200, zero 5xx), payload key rotation |

Two caveats apply across the board:

- **Live results are point-in-time.** Nothing re-runs them automatically. A GitHub API change would surface first as a failing scheduled sync in production, not in CI, because CI replays recorded fixtures.
- **Benchmarks ran on one machine.** They establish that the design has headroom (most gates pass by 5× or more), not what production hardware will do. Year-one capacity (100M findings, 1,000 connections) was closed on per-partition evidence by owner decision, not a full-size run: 2,375 bytes per finding means about 237 GB, or 1.56M rows per partition across 64 partitions, which is the size the API gates were measured at.

## 5. Known gaps and risks

Grouped by what they block. "Severity" is the impact if nothing is done before a production launch.

### 5.1 Production substrate

| Gap | Evidence | Severity | Next step |
|---|---|---|---|
| **No KMS key provider.** Only the local KEK exists; any other `VAULT_KEY_PROVIDER` raises at startup. | `packages/domain/src/securefabric_domain/runtime.py` rejects anything but `local`; `.env.example` marks `aws_kms` as "production, later". | High | Implement a `KeyProvider` for the chosen cloud KMS (wrap with the public key stays local; unwrap moves into KMS). Needs the hosting decision (section 7). |
| **No deployment definition.** There are Dockerfiles and compose stacks, but no infrastructure as code, no deploy pipeline and no production configuration. | Only `.github/workflows/ci.yml` exists; no IaC in the repo. | High | Choose hosting, then write the deploy pipeline with the rolling-deploy drill as its acceptance test. |
| **One region.** Region is enforced per key, but only one cell exists (PD-15, NFR-10 excluded). | Plan traceability. | Medium | Deployment work once a second region is needed. |
| **Clients not published.** `@securefabric/client` 0.1.0 and `securefabric-client` build and were validated live, but are unpublished by owner decision. | `progress.md`, "Blocked on the owner". | Low | Publish when the API is ready for external customers. |

| **The containerised stack is not configured.** `compose.yaml` passes only `DATABASE_URL` to the API and worker, so `make up` starts them without vault keys, pepper, cursor key or blob settings (the raw archive silently falls back to an in-memory store). Local development works because `make dev` runs on the host with `.env`. | `compose.yaml` (`x-app-env`), `runtime.py` (`MemoryBlobStore` fallback). | Medium | Pass the `.env` through (`env_file`) and fail fast instead of falling back to memory outside tests. |
| **Absurd task cleanup does not run on its own.** Retention for finished Absurd tasks needs pg_cron or a scheduled call; today it is `make absurd-cleanup`. | `Makefile`, [Part 9](09-operations-and-reliability.md). | Medium | Spawn `absurd.cleanup_all_queues()` from the maintenance role. |
| **Alerts are rows, not pages.** An alert writes `obs.alert`, a log line and a status count; nothing notifies a human. | `obs.py`, [Part 9](09-operations-and-reliability.md). | High for launch | Route raised alerts to the on-call tool of the chosen hosting. |

### 5.2 Issues found while writing this series

Writing the series meant reading every subsystem against its claims. These are the issues that came out of it. Each is described with its evidence in the part named; the ones marked ✔ were re-checked against the code for this summary. None of them shows up in the existing tests, which is why they survived a green `make verify`.

| Issue | Part | Severity |
|---|---|---|
| ✔ **Open redirect after sign-in.** `/login` takes `return_to` from the query string and `/callback` accepts any value starting with `/`, so `//evil.example` sends a freshly signed-in user to another host. | [8](08-dashboard-and-clients.md) | High |
| ✔ **Secrets kept in plaintext for 24 h in the idempotency cache.** `POST /v1/api_keys` and webhook-endpoint creation accept `Idempotency-Key` (the dashboard always sends one), and the stored replay response holds the new key or signing secret unencrypted in `control.idempotency_key`. | [7](07-public-api-and-events.md) | High |
| ✔ **`sf_api`'s grants are broader than documented** (see D-5). Tenant tables are protected by RLS regardless, but tables without RLS are not: `control.account`, `control.app_user`, `control.membership`, `obs.alert`, `obs.worker_heartbeat`, `obs.api_rate_counter`, `sync.ingress_delivery`, `sync.rate_bucket` and the Absurd tables are readable and writable by the API role, guarded only by application code. Confirm against the live database, then revoke what the definer functions already cover. | [2](02-tenancy-identity-and-security.md), [9](09-operations-and-reliability.md) | Medium |
| ✔ **A `RUNNING` run whose Absurd task is gone is never cleaned up.** Past its deadline the scheduler only sets `cancel_requested`; if no worker holds the task, the run stays `RUNNING`, blocks its stream and holds cap slots. | [4](04-sync-engine.md) | Medium |
| ✔ **GitHub cursor-rejection restart is untested.** `_walk` implements it, but FakeGitHub never rejects a cursor; `progress.md` (spike S4) says the conformance suite covers it. | [5](05-connector-platform.md) | Medium |
| ✔ **GitHub's per-minute secondary budget is declared but not enforced** (`budget.per_minute_points` is never read), so secondary limits are handled reactively only. | [5](05-connector-platform.md) | Low |
| **`GET /v1/events` can skip events**: it pages by an id assigned before commit, with no lag guard. | [7](07-public-api-and-events.md) | Medium |
| **Events emitted while an endpoint is disabled get no delivery row**, so range replay cannot recover them. | [7](07-public-api-and-events.md) | Medium |
| **The organization-scope 5 s visibility rule is not enforced as documented**: the pool sets a statement timeout, not a guard on uncommitted visibility. | [3](03-data-model-and-record-store.md) | Low |
| **A targeted refresh can drop a webhook that arrives during its fetch**; the next scheduled pass repairs it. | [4](04-sync-engine.md) | Low |
| **Connect page framing**: `frame-ancestors *`, and the embedder `origin` parameter is trusted without checking it against the session's allowed origins. | [8](08-dashboard-and-clients.md) | Medium |
| **Customer status view shows worker ids**, which default to `hostname:pid`. | [9](09-operations-and-reliability.md) | Low |
| **Coverage holes**: no tests for the dashboard's server routes (proxy, session, login/callback, connect token swap); the generated isolation suite skips paths keyed by several id types; no direct test for `DbRateBudget`; no drift check for the Python client. | [4](04-sync-engine.md), [7](07-public-api-and-events.md), [8](08-dashboard-and-clients.md) | Medium |
| ✔ **WorkOS session tokens are verified without an audience check** (`verify_aud: False` in `workos.py`). The signing key comes from this client's JWKS, which limits the exposure, but the claim should be checked. There are no automated tests for session verification. | [2](02-tenancy-identity-and-security.md) | Medium |
| **The API can hold the master key.** When `VAULT_KEK_PUBLIC_KEY` is unset, the API derives its wrap key from `VAULT_MASTER_KEY`, so the unwrap secret sits in the API's environment and nothing refuses it. Environment key rotation is not built (the `vault_previous_*` columns are never written). | [2](02-tenancy-identity-and-security.md) | Medium |
| ✔ **`connect.complete` is not crash-safe.** It clears `callback_sealed` before calling the vendor, so a retry after a crash fails and the connection stays `PENDING` until the 7-day cleanup. | [6](06-connections-and-connect-flow.md) | Medium |
| **Connect-flow edges not finished**: GitHub "choose an installation" stores choices nothing reads; owner-approval installs never complete (deleted after 7 days); a rotation or re-authorisation can point a connection at a different vendor tenant unchecked; connect sessions' single-use, 410 and redirect-origin rules have no automated tests. | [6](06-connections-and-connect-flow.md) | Medium |
| **Documented-but-different**: the API rate limiter is fixed one-minute windows, not a token bucket; only ten POSTs honour `Idempotency-Key`; deprecation headers (API-09) and an OpenAPI breaking-change gate (API-14) do not exist; only retention and purge write audit events. | [7](07-public-api-and-events.md), [9](09-operations-and-reliability.md) | Low |

### 5.3 Sustained evidence

| Gap | Evidence | Severity | Next step |
|---|---|---|---|
| **No nightly live sync.** Conformance runs on recorded fixtures; nothing exercises real GitHub on a schedule. | CI triggers only on push and pull request. | High | A scheduled workflow (or a production canary connection) that syncs the seeded `securefabric` org and fails on any non-HEALTHY outcome. This is definition-of-done item 1. |
| **Benchmarks not on production hardware**, and two gates not run: the 1M-finding backfill (< 2 h) and autovacuum under a 100M-row weekly reconcile (< 20% dead tuples per partition). | `progress.md` M10. | Medium | Re-run `make bench` on the production database class; add the two missing gates. Expect read-latency spikes after very large backfills until autovacuum catches up (observed at 1M); partition-level autovacuum settings are the planned mitigation. |
| **GHES verified only through fakes and GitHub's published API descriptions.** Version gating is tested against FakeGitHub at 3.4 and 3.10. | `test_old_ghes_gates_streams_and_lists_per_repository`; plan decision 7 (no GHES access). | Medium | Run the conformance flow against a real GHES or GHE.com instance before selling to a GHES customer. |
| **Spike fallbacks still in force.** S3 keeps daily reconciles; S2 sends selected-repository installs to per-repo listing. | `progress.md` spikes table. | Low | Confirm `updated_at` behaviour live and relax to weekly; test org listings with a selected-repo install. |
| **The M8 exit test is not done.** No one other than the CDK's author has built a connector. | Definition of done item 3. | Medium | Have the next connector (Tenable or a tier-A one like Semgrep) written by someone new, and log every place they had to touch outside `packages/connectors/`. |

### 5.4 Deferred scope

The plan excludes these by id (see [its traceability table](../plan/10-delivery-plan.md#5-requirement-traceability)). None is half-built; each is either absent or a reserved hook.

| Area | Not built |
|---|---|
| Identity | SSO and SCIM (TEN-10), enforced 2FA (TEN-11), roles finer than admin/member (TEN-09). All WorkOS configuration. |
| Credentials | Relay agent (AUTH-13), mutual TLS (AUTH-14), AWS role mode beyond an interface (AUTH-01), Microsoft admin consent (AUTH-02). |
| Data | Destination connections (CON-15, column reserved), bulk export (API-15), customer bucket export (STORE-15), a second store beyond a hook (STORE-08), cross-vendor correlation (DEDUP-02/03/04). |
| Events | Record-level events (CDC-05), streaming destinations (CDC-06), per-connection webhook overrides (HOOK-09). |
| Customer observability | OTLP export to customers (OBS-04), customer-defined alerts (OBS-05), a public status page (OBS-06). |
| Operations | Feature flags beyond per-environment integrations (OPS-04), quota enforcement (BILL-02), cost reporting (NFR-11), external availability probes (NFR-01). |
| Write-back | Ticket creation (ACT-01), which needs a ticketing connector. |
| Security | Customer-managed keys (SEC-03; rotation is built), a penetration test (SEC-10). |

### 5.5 Risks to watch

| Risk | Why it matters | Mitigation in place |
|---|---|---|
| Postgres is the single scaling limit | Queues, locks, the outbox, logs and data share one database. | Gates pass with large headroom; logs and audit sit behind interfaces that can move to another store; hot tables are partitioned. Watch admission lag, outbox lag and autovacuum. |
| One shared GitHub App for all github.com tenants | A suspension or rate-limit policy change hits every tenant at once. | Customer-owned apps are supported per environment. |
| Fixture drift | Recorded GitHub fixtures age while GitHub's API evolves. | `securefabric-admin record` re-records from the seeded org; a nightly live sync (5.3) would catch drift first. |
| Shared-cell blast radius | Every tenant shares one database and one set of workers. | RLS, per-tenant admission fairness and caps, per-environment API rate limits. |

## 6. Roadmap

Ordered by what unblocks a production launch first.

**Step 1: fix what this review found**

1. Close the High items in 5.2 (open redirect, plaintext secrets in the idempotency cache), then the Medium ones, each with the regression test that would have caught it.
2. Correct `progress.md` where it overstates: the S4 cursor-restart test, `sf_api`'s rights, and the WorkOS session test it cites.

**Step 2: make it deployable**

3. Decide hosting, region, managed Postgres and KMS (section 7, item 8).
4. Implement the KMS `KeyProvider`, keep the master key out of the API's environment, and run the restore drill against it.
5. Write the deploy pipeline with a configured container stack; gate it on the rolling-deploy drill.
6. Route alerts to on-call, and add the nightly live sync against the seeded org, alerting on any unhealthy outcome.

**Step 3: prove it at size**

7. Re-run the benchmark gates on production-class hardware, and add the backfill and autovacuum gates.
8. Confirm spike S3 live and relax the alert streams to weekly reconciles.
9. Run the GitHub flow against a real GHES instance.

**Step 4: widen it**

10. Build the next connector with someone who did not write the CDK (the M8 exit test), starting with a tier-A vendor.
11. Publish the clients.
12. Pick up deferred scope by customer demand, starting with SSO/SCIM (WorkOS configuration) and bulk export.

## 7. Open decisions for the owner

The plan listed eight decisions with defaults ([section 7](../plan/10-delivery-plan.md#7-decisions-that-need-you)). Their state now:

| # | Decision | State |
|---|---|---|
| 1 | Platform versus February connector count | **Open.** The platform is complete; the connector count depends on how fast the next connectors land (roadmap item 8). |
| 2 | Replace the mock schema and domain | **Resolved:** replaced. |
| 3 | Shared GitHub App as default | **Resolved:** shared by default, customer-owned supported. |
| 4 | Secret finding severity | **Resolved:** `UNKNOWN` by default, with the `secret_severity` option to derive it. |
| 5 | Dropping the Contents permission | **Resolved:** not requested; the manifest asks for Metadata, the three alert permissions (read, and optionally write for write-back), and optional Administration read. |
| 6 | Write-back in scope | **Resolved:** built for all three GitHub alert families. |
| 7 | GHES or GHE.com access | **Open.** Without it, GHES support is verified only against fakes and published API descriptions. |
| 8 | Region and hosting | **Open, and now the critical path.** Blocks the KMS provider and deployment. |
| — | Publishing the clients | **Decided 2026-11-23:** not yet. |

## Further reading

- [../plan/10-delivery-plan.md](../plan/10-delivery-plan.md): milestones, traceability, spikes and the definition of done
- [../../progress.md](../../progress.md): the validation record behind every status above
- [Part 9](09-operations-and-reliability.md): benchmark details, drills and CI gates
- [Part 2](02-tenancy-identity-and-security.md): the vault and key hierarchy the KMS work changes
