# Part 1: Architecture

## 1. Processes

The platform is a modular monolith in Python 3.13 on one Postgres 17 database. It runs as one image with several roles, split by what each role is trusted to do.

| Role | Entrypoint | Does | Can open the vault |
|---|---|---|---|
| `api` | `securefabric-api` | Public and dashboard HTTP API, connect-flow endpoints, inbound vendor webhooks, writes outbox rows | No |
| `scheduler` | `securefabric-worker --role scheduler` | Fires due schedules, admits stream runs into Absurd, expires stuck runs, dispatches outbox events, runs retention | No |
| `sync` worker | `securefabric-worker --role sync` | Runs connector streams: fetch, normalise, write | Yes |
| `control` worker | `securefabric-worker --role control` | Credential verification, permission probes, token refresh, connection lifecycle, actions (write-back), purge | Yes |
| `delivery` worker | `securefabric-worker --role delivery` | Outbound webhook delivery | Webhook signing secrets only |

`scheduler` is a singleton by leader election (a session advisory lock), so any number of copies can run and one is active. Every other role scales horizontally and holds no state (NFR-07).

Supporting services: Postgres, and an S3-compatible object store for the raw page archive (MinIO in `compose.yaml`, S3 in production). There is no Redis and no message broker. Locks are Postgres advisory locks, rate budgets are Postgres rows, and the outbox is a Postgres table.

## 2. Package layout

The repo's existing split (apps import packages, packages never import apps) stays. New and changed members:

```
apps/
  api/            FastAPI app. Routers per resource family, two authenticators, problem+json errors.
  worker/         One process, four roles. Handlers per queue.
  dash/           Next.js dashboard. Also hosts the connect UI at /connect/[token].
packages/
  core/           (keep) settings base, logging, error types. Add: ids, clock, crypto primitives.
  db/             (keep) pool and migration runner. Add: tenant-scoped transaction helper for RLS.
  tasks/          (keep) TaskSpec contracts. Replace the two demo contracts with the real ones.
  schema/         (new) Canonical models: Resource, VulnerabilityFinding, enums, health codes,
                  event envelopes. Pydantic. The single source for validation, OpenAPI and docs.
  cdk/            (new) Connector development kit: manifest schema, stream interface, HTTP client,
                  pagination, error taxonomy, fixture recorder, conformance tests, dry-run CLI.
  connectors/     (new) First-party connectors: github/, sandbox/. Each is manifest + module + fixtures.
  domain/         (rewrite) The platform's services, one subpackage per module:
                  tenancy, catalog, vault, connections, sync, records, events, obs, actions.
  client/         (keep) Generated TypeScript client.
  connect-js/     (new) Small embeddable loader for the connect UI (iframe + postMessage).
  ui/, tokens/, config/   (keep)
db/migrations/    0001 stays (Absurd). 0002 is replaced by the real schema (see section 5).
tools/
  github-seed/    (new) Scripts that create and maintain the seeded GitHub test organisation.
```

Import rules, enforced by a lint check in CI:

- `connectors` may import only `cdk` and `schema`. Connector code never touches the database, the vault or an HTTP library directly (CDK-03).
- `cdk` may import `schema` and `core`. It defines ports (interfaces) for rate budget, raw capture and credential access, which `domain` implements.
- `domain` may import everything below it. `api` and `worker` are thin adapters over `domain`.
- `schema` imports nothing of ours.

This layering is what makes a future connector a pure addition: it lives entirely in `packages/connectors/<vendor>/`.

## 3. Trust boundaries

1. **API cannot read vendor credentials.** Credentials arrive at the API, are sealed to the environment's public key before the request handler returns, and are stored as ciphertext. The API process has no private key. Verification of new credentials is therefore a worker task, which is also what the requirement asks for (a connection is PENDING, then ACTIVE after verification).
2. **Inbound webhook secrets are separate.** The API must verify GitHub signatures, so each vendor app's webhook secret is encrypted under a distinct ingress key the API does hold. Leaking that key lets an attacker forge webhooks, which at worst trigger extra syncs, because webhook payloads are never trusted as data (part 6, section 8).
3. **Tenant isolation is enforced twice.** Every query goes through repository functions that take an `environment_id`, and Postgres row-level security checks the same id from a transaction-local setting. A missing filter in application code fails closed.
4. **Connector code is ours.** No customer code runs anywhere (SEC-06), so there is no sandbox. Connector dependencies are allowlisted in CI.
5. **Egress.** Every outbound call, to vendors and to customer webhook endpoints, goes through one HTTP layer that resolves DNS itself, rejects private, loopback, link-local and metadata addresses, pins the resolved address for the connection, and caps redirects (RATE-07, HOOK-08, AUTH-12).

## 4. How the main flows cross the system

**Connect.** Customer backend creates a connect session → end user opens the connect UI → for GitHub, a redirect to the app installation page and back → API binds the installation to a PENDING connection and enqueues `connection.verify` → control worker mints an installation token, probes each stream's endpoint, records per-stream grants, sets ACTIVE → scheduler creates schedules and an INITIAL job.

**Sync.** Scheduler finds due schedules → creates a job with one stream run per due stream → admission picks runs by priority and fairness within concurrency caps and spawns one Absurd task per run → sync worker loads the connector, opens the credential, and loops: reserve rate budget, fetch a page, archive the raw page, normalise, validate, upsert the batch and save the checkpoint in one transaction → at the end, sweep if it was a full pass, write counts, emit `sync.completed` to the outbox in the same transaction as the final state.

**Read.** Customer calls `GET /v1/vulnerability_findings` with an API key and `X-CONNECTION-ID` → API authenticates, opens a tenant-scoped transaction, runs a keyset query on one partition, returns Leen-shaped JSON with an opaque cursor.

**React.** GitHub sends `dependabot_alert` → API verifies the signature, stores the delivery idempotently, resolves the installation to connections, and marks that alert dirty → scheduler admits a targeted refresh at high priority → sync worker fetches that one alert from GitHub and writes it through the normal path.

## 5. What happens to the existing repo

| Existing piece | Disposition |
|---|---|
| Turborepo, uv workspace, Makefile, CI, git hooks, Dockerfile, compose | Keep. Add the object store service, worker roles, and the new packages to the task graph. |
| `packages/core`, `packages/db`, migration runner | Keep and extend. |
| `packages/tasks` `TaskSpec` | Keep the mechanism. Replace `PROVISION_TENANT` and `SYNC_CONNECTION` with real contracts. Add queues `sync_interactive`, `sync_bulk`, `control`, `delivery`, `maintenance`. |
| Pydantic → OpenAPI → `packages/client` codegen with `check-generated` | Keep. This is the backbone of dashboard correctness. |
| `apps/api` app factory, request-id middleware, health routes | Keep. Change the error envelope to RFC 9457 problem+json (API-06) and the path prefix from `/api/v1` to `/v1` (API-09). |
| `db/migrations/0002_control_plane.sql` (`fabric.*`) | Replace. It is a single-workspace mock with text ids and plaintext secrets, and nothing is deployed. The new schema starts at 0002. The file header's "never edit after applied" rule starts to bind from the first real deployment. |
| `packages/domain` (`service.py`, `repository.py`, `seed.py`, `catalog.json`) | Rewrite as the real domain. The catalog moves from a hand-written TypeScript file to connector manifests (part 5, section 2). |
| `apps/dash` shell, data-table kit, design tokens, command palette | Keep. Views are rewired from the localStorage mock to the real API one at a time (part 8). |
| `apps/dash` mock store, `lib/catalog.ts`, simulated playground endpoints, 15 `ModelKey`s | Remove as each view is rewired. The model list shrinks to what exists: resources and vulnerability findings. |
| Dashboard "customer" on a connection | Becomes Organization. |
| Workflows demo page and tenant-provisioning task | Remove once the Jobs view exists. Habitat remains the low-level task inspector in development. |

The README also needs correcting: it describes `apps/web`, which is now `apps/dash`, and references `make` targets that do not exist (`seed`, `status`, `dev-web`).

## 6. Decision log

Each entry states what was chosen, what was rejected and what would make us revisit. Requirement decisions D1 to D10 stand as written. These are the additional ones this plan makes.

**PD-1: Absurd plus an admission layer, not a custom queue and not Temporal.**
The requirements (D3) call for a Postgres queue modelled on Nango's scheduler, with priority, fairness and backoff added. The repo already vendors Absurd, which provides durable leases with claim timeouts, crash recovery, cancellation policies, idempotent spawn and durable sleeps, all in Postgres. What Absurd lacks is ordering control: `claim_task` takes runs in `available_at` order with no priority, no fairness and no keyed concurrency. Rather than fork it, the plan keeps every scheduling decision in our own `sync.stream_run` table and lets the scheduler decide which runs enter Absurd and when. A run that is queued, parked for a rate limit, or waiting to retry is simply a row that has not been admitted. Absurd only ever holds work that is allowed to run now, so FIFO inside it is harmless.
Rejected: a custom queue (rebuilds leases and crash recovery we already have), forking Absurd's SQL (upgrade burden), Temporal (a second stateful system, and checkpoints already make runs resumable).
Revisit if admission becomes a throughput bottleneck above roughly 200 admitted runs per second.

**PD-2: GITHUB and SANDBOX as the two reference connectors.** See the README. Rejected: building Tenable alongside GitHub to get breadth, because test-tenant access and vendor quirks would slow the platform, and a synthetic vendor can inject failures a real one cannot.

**PD-3: Integration sits between connector and connection.**
A connector is code and a manifest, global and versioned. An integration is one environment's use of a connector: enabled streams, default intervals, default options and which vendor app registration to use. A connection belongs to one organization and one integration. For Leen compatibility, creating a connection with only `vendor: "GITHUB"` resolves to the environment's default integration for that connector, creating it on first use, so the simple path has no extra step.
Rejected: connector → connection directly (nowhere to put a customer-owned GitHub App or per-environment defaults, and the dashboard already has an integrations concept).

**PD-4: Sealed-box vault with the private key held only by workers.**
Each environment has an X25519 key pair. The API seals with the public key. The private key is stored wrapped by a key-encryption key that only worker roles can use (a local master key in development, a cloud KMS key in production, behind one `KeyProvider` interface). Sealed boxes carry no associated data, so the binding the requirements ask for (SEC-02: ciphertext copied to another connection must not decrypt) is done by putting `{environment_id, connection_id, purpose}` inside the plaintext envelope and rejecting a mismatch on open.
Rejected: one symmetric data key per environment used by both API and workers (simpler, but the API tier could then decrypt everything).
This satisfies the intent of SEC-04 by construction: there is no credential-reading API for a token to protect.

**PD-5: Typed canonical tables with `seen_gen`.** Part 2, sections 4 and 6, and part 4, section 8.

**PD-6: Monotonic `updated_at` under the write lock.** Part 4, section 7.

**PD-7: Replace the mock schema.** Section 5 above.

**PD-8: One API, two authenticators.** Part 7, section 1. The dashboard uses the same endpoints as customers, plus a small set of management endpoints (members, environments) that only a session can call.

**PD-9: Leen V2 wire compatibility.** Public JSON is snake_case with Leen's field names, and query parameters keep Leen's camelCase (`updatedSince`). Dashboard-only models currently emit camelCase. They change to snake_case so there is one convention.

**PD-10: Shared GitHub App by default, customer-owned app per environment supported.** Part 6, section 2.

**PD-11: Webhooks never carry data into the store.**
An inbound webhook marks a record dirty and the worker re-fetches it from the vendor. Rejected: normalising the payload directly, which is one request cheaper but exposes us to out-of-order deliveries, forged payloads if the ingress key leaks, and payload shapes that differ subtly from the REST shape. Scheduled sync remains the source of truth, and webhooks only shorten latency.

**PD-12: Vendor payloads are stored as opaque bytes from day one.**
`vendor_data` is a `bytea` column holding compressed JSON with a one-byte format header. Application-level encryption of payloads (STORE-09, P1) then becomes a format value, not a migration. The cost is that vendor payloads cannot be queried in SQL, which is intended: anything worth filtering on belongs in a canonical column.

**PD-13: Retries are ours, crash recovery is Absurd's.**
A classified failure (vendor 5xx, timeout) ends the Absurd task normally with outcome `retry`, and the run row waits for its next attempt on our schedule of 1, 5, 15 and 60 minutes (SYNC-10). Non-retryable outcomes skip retries. Absurd's own `max_attempts` covers only the case where a worker dies mid-task. This keeps one place where attempt history, backoff and health classification live.

**PD-14: Logs and audit start in Postgres.**
Operation logs are daily range partitions with 30-day retention. Audit and usage events are monthly partitions. All three sit behind a small writer and reader interface so they can move to a column store when volume demands it, as the requirements anticipate.

**PD-15: One cell, region as configuration.**
The plan builds one deployable cell. Region is a deployment setting that is baked into API key prefixes and checked on every request, so a key from another region is rejected (API-10). Standing up a second region is deployment work outside this plan.
