# SecureFabric

A unified security-data API. Customers connect their vendors (GitHub today, more through the
connector SDK); SecureFabric syncs resources and vulnerability findings into one canonical,
**Leen V2-compatible** model, keeps them fresh, and serves them over a public REST API with
webhooks. The design lives in [`docs/plan/`](docs/plan/00-README.md); build status in
[`progress.md`](progress.md).

```
 dashboard / customers ──► FastAPI (/v1, problem+json, API keys or WorkOS sessions)
                               │  writes rows + outbox in one transaction
                               ▼
                     Postgres 17: control · sync · data · events · obs  (RLS per environment)
                               ▲                                ▲
   scheduler ── admits stream runs ──► Absurd queues ──► workers (sync · control · delivery · maintenance)
                                                             │  connectors (packages/connectors) via the CDK
                                                             ▼
                                                     vendor APIs (GitHub, SANDBOX…) · MinIO (raw pages)
```

## Quick start

```bash
make bootstrap   # check uv/node/pnpm/docker, create .env, install deps and git hooks
make dev         # Postgres + MinIO (Docker), migrations, api, worker, dash, client watcher
make seed        # bootstrap the platform; demo account, environment, API key, SANDBOX connection
make status      # is everything up, migrated and draining?
```

| URL | What |
|---|---|
| http://localhost:3000 | Dashboard (WorkOS sign-in, or `SF_DEV_API_KEY` in `apps/dash/.env.local`) |
| http://localhost:8000/docs | Swagger UI for the public API |
| http://localhost:8000/v1/status | System status (summary without credentials; more with a key) |
| http://localhost:9001 | MinIO console (raw page archive) |
| http://localhost:7890 | Habitat, Absurd's dashboard (`make habitat`; dev only) |

For vendor redirects and webhooks the API must be public: run
`ngrok http --url=<your sticky domain> 8000` and set `PUBLIC_API_URL` to it.

## Layout

```
apps/
  api/          FastAPI: the public /v1 API, connect flow, ingress webhooks, status         (Python)
  worker/       Absurd worker; roles: scheduler, sync, control, delivery, maintenance     (Python)
  dash/         Next.js dashboard and the hosted connect UI                               (TS)
packages/
  core/         settings, logging with redaction, ids, canonical JSON, crypto (vault)     (Python)
  db/           role-bound psycopg pools, tenant transactions, migration runner           (Python)
  schema/       canonical records (Leen V2 shapes), enums, event envelope                 (Python)
  cdk/          connector SDK: manifest, HTTP client, egress policy, pagination, fixtures (Python)
  connectors/   GitHub and SANDBOX connectors (manifest, mapping, golden output)          (Python)
  domain/       tenancy, connections, write path, sync engine, events, ops, enrichment    (Python)
  tasks/        Absurd queues and typed task contracts                                    (Python)
  client/       TS API client generated from the OpenAPI document                         (TS)
  connect-js/   embeddable connect flow (modal or popup)                                  (TS)
  ui/ tokens/ config/   design system and shared TS config                                (TS)
db/migrations/  forward-only SQL: 0001 Absurd, 0002 platform schema + RLS, 0003+ additions
scripts/        status.py (`make status`), demo.py (`make demo`)
```

Dependencies flow one way: `apps → packages`. Connector code may import only the CDK, the
schema package, its own package and the standard library (`securefabric-cdk lint-imports`,
enforced by a test).

## How it works

- **Tenancy.** Accounts hold environments (dev, prod). Every tenant table has row-level security
  keyed on `app.environment_id`; the API runs as `sf_api`, workers as `sf_worker`, cross-tenant
  jobs as `sf_system`. A missing tenant setting reads zero rows (`packages/db/tests/test_rls.py`).
- **Vault.** Credentials are sealed to the environment's X25519 key. The API can seal but never
  unwrap; only workers open them, and every envelope is bound to its connection and purpose.
- **Sync engine.** Schedules create jobs and stream runs; the scheduler (leader-elected) admits
  runs fairly under per-budget, connection, environment and connector caps, and spawns one Absurd
  task per slice. Runs park on rate limits instead of holding a worker, retry classified
  failures at 1/5/15/60 minutes, and checkpoint per page.
- **Write path.** `records.apply_batch` upserts hash-gated rows with a monotonic per-object
  clock, derives REOPENED/undelete, records state history, and sweeps deletions after full passes
  (with a guard). Raw vendor pages are sealed and archived to the object store first.
- **Events.** Every state change writes an outbox row in the same transaction; delivery signs
  `v1=` HMAC over `{ts}.{body}` and retries for 24 hours.
- **Connectors.** A manifest (streams, auth, options, write-back) plus code against the CDK.
  Each connector passes the 11-check conformance suite and golden output tests.

## Make targets you will use

```bash
make status                 # toolchain, services, migrations, processes, workspace, queues, drift, git
make status-api API_KEY=…   # GET /v1/status from the running API
make demo API_KEY=… CONNECTION=<id> [API_URL=…]   # on-demand sync, followed to the end
make verify                 # everything CI runs (lockfiles, lint, types, tests, drift, ultracite)
make generate               # regenerate packages/client/src/v1.ts from the API
make db-migrate             # apply pending migrations; make db-new-migration name=…
make test-connectors        # conformance + golden; also test-api, test-domain, test-db, test-cdk…
make tasks q=control        # inspect an Absurd queue (sync_interactive, sync_bulk, delivery, maintenance)
make docs-connectors        # regenerate docs/connectors/*.md and capabilities.json from each connector
make bench-absurd           # queue throughput; also tools/bench/ingest.py and tools/bench/api_latency.py
```

Run `make` with no target for the full list.

## Operating

- **Admin CLI** (`securefabric-admin`): `bootstrap` (platform apps from `.env`), `seed`,
  `operator <email>` (grant operator access), `dryrun` / `record --connection <id> --stream <s>`
  (read a live stream without persisting; record scrubbed fixtures).
- **Operator console**: `/[env]/admin` in the dashboard (alerts with runbooks, cross-account
  search, scheduler, audited repairs and raw pages). Runbooks live in `docs/runbooks/`.
- **Connector CLI** (`securefabric-cdk`): `validate`, `new`, `capabilities [--check]`,
  `scan-fixtures`, `lint-imports`, `schema`.
- **Status** has three audiences: anyone sees the summary; API keys and sessions also see
  workers, queues and run counts; operators see host names and the open alerts.
- **Metrics** (OPS-03) are OpenTelemetry: set `OTEL_EXPORTER_OTLP_ENDPOINT` and every service
  exports over OTLP/HTTP; without it the meter is a no-op.
- **Payload encryption** (STORE-09): set `PAYLOAD_KEYS` and stored vendor payloads are sealed
  with AES-256-GCM, bound to their row; the `payload_reencrypt` maintenance job seals older rows
  and re-seals after a key rotation (add a version, wait for `remaining: 0`, drop the old one).
- **Alerts** carry runbook links (`GET /v1/admin/alerts` and `POST /v1/admin/alerts/{id}/resolve` for operators); maintenance jobs handle
  partitions, retention, purges, token refresh sweeps and enrichment (NVD, KEV, EPSS, OSV).

## Configuration

pydantic-settings, one prefix per service: `DATABASE_*`, `ABSURD_*`, `API_*`, `WORKER_*`,
plus platform settings (`PUBLIC_API_URL`, `VAULT_*`, `INGRESS_KEY`, `BLOB_*`, `WORKOS_*`,
`GITHUB_APP_*`, `NVD_API_KEY`). `.env.example` lists every variable; the dashboard's are in
`apps/dash/.env.example`. Real environment variables win over `.env`.

## Database migrations

`securefabric-migrate` applies `db/migrations/*.sql` in order, one transaction per file, under an
advisory lock, and refuses to run if an applied file's checksum changed. Never edit an applied
migration: add a new one. Tests use their own databases (`securefabric_test*`) and never fall
back to `DATABASE_URL`.

## Testing

```bash
make test        # every package via turbo; integration tests need Postgres (make db-up)
make verify      # what CI runs
```

Python tests run against real Postgres and Absurd. Connectors are tested against in-process
vendors (the SANDBOX vendor, `FakeGitHub`) through the real executor, so conformance covers the
whole pipeline without network access.
