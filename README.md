# SecureFabric

A **Turborepo** monorepo with two toolchains:

- **Python** (uv workspace): a **FastAPI** API, an **[Absurd](https://earendil-works.github.io/absurd/)** worker (durable workflows using nothing but Postgres), and the **control-plane domain** behind the dashboard.
- **TypeScript** (pnpm workspace): **`apps/dash`**, the Next.js dashboard, plus a shared UI kit, design tokens, and a **typed API client generated from the FastAPI schema**.

```
apps/dash ──(@securefabric/client, typed)──► /api/v1/* (FastAPI) ──► packages/domain ──► Postgres (schema fabric)
    ▲                                              │ POST …/connections, …/sync
    │  GET /api/v1/workspace                       └──► Absurd queue ──► worker: durable sleep → finish_sync (one txn)
    └──── (polled: 1s while syncs run, 10s idle) ◄──────────────── job SUCCESS, counts, health, logs, webhooks ┘
```

## Quick start

```bash
make bootstrap   # checks uv/node/pnpm/docker, creates .env, installs deps, installs git hooks
make dev         # postgres (Docker) + migrations + api + worker + dash + client watcher, all hot-reloading
make status      # in another terminal: is everything up, migrated, seeded and in sync?
```

| URL | What |
|---|---|
| http://localhost:3000 | **Dash**. Everything it shows comes from the API; the demo workspace seeds itself on first load |
| http://localhost:3000/dev/status | **Status page**: API, database, migrations, workers, queues, workspace health |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/api/v1/status | The same status as JSON |
| http://localhost:7890 | **Habitat**, Absurd's dashboard (`make habitat`; dev only, no auth) |

If you'd rather run the API and worker in Docker: `make stack` (Postgres, api, worker and Habitat with hot reload), then `make dev-dash` for the dash.

Run `make` with no target to list every command. Every target wraps a `pnpm`/`turbo`/`uv` command, so you can call those directly.

## Status: what state is everything in?

```bash
make status        # toolchain, deps, Docker services, Postgres + migrations, API/dash/worker,
                   # workspace + queues, generated-code drift, git. Ends with next steps.
make status-fast   # skip the drift checks
make status-json   # machine-readable (ARGS=--strict exits 1 if anything is down)
make status-api    # ask the running API (GET /api/v1/status)
```

A typical report when the worker isn't running:

```
Processes
  ✔ api             http://localhost:8000 · ready=ok
  ✔ dash            http://localhost:3000
  ✖ worker          none online

Something is down. (1.3s)
Next steps:
  → worker: make dev (or make dev-worker)
```

Database facts come from `securefabric_domain.status.collect`, the same function behind `GET /api/v1/status` and the dash's Status page, so the three never disagree. Worker liveness comes from `fabric.worker_heartbeats`: each worker upserts its row every 5s and counts as offline after 20s of silence. Syncs that stay `RUNNING` for over 2 minutes are flagged as stuck, which almost always means no worker is running.

## Layout

```
apps/
  api/        api                    FastAPI: the control-plane API, status, durable tasks       (Python)
  worker/     worker                 Absurd worker: connection syncs, tenant provisioning, heartbeat (Python)
  dash/       dash                   Next.js 16 dashboard: connections, integrations, logs, keys… (TS)
packages/
  core/       @securefabric/core     settings base, structlog logging, domain errors             (Python)
  db/         @securefabric/db       psycopg pool + forward-only SQL migration runner            (Python)
  domain/     @securefabric/domain   control plane: models, services, seed, status               (Python)
  tasks/      @securefabric/tasks    typed task contracts (TaskSpec) shared by api and worker    (Python)
  client/     @securefabric/client   typed API client generated from the OpenAPI schema          (TS)
  ui/         @securefabric/ui       shadcn/base-ui components + globals.css                     (TS)
  tokens/     @securefabric/tokens   design tokens → theme.css, tokens.ts, DESIGN.md             (TS)
  config/     @securefabric/config   shared tsconfig                                             (TS)
db/migrations/                       0001 pinned Absurd schema (v0.5.1) · 0002 control plane (fabric.*)
scripts/status.py                    `make status`
docker/                              Habitat + absurdctl images, Postgres init scripts
turbo.json                           the task graph (lint, typecheck, test, build, check-*, dev)
.husky/                              git hooks: pre-commit, commit-msg, pre-push
```

**How the two toolchains share one graph.** Each Python member has a thin `package.json`. It declares its workspace dependencies (`api` → `@securefabric/{core,db,domain,tasks}`) and has `lint`/`typecheck`/`test` scripts that call `uv run ruff|mypy|pytest`. Turborepo can then order, parallelise and **cache** Python tasks alongside the TypeScript ones. Real Python dependencies still live in `pyproject.toml` + `uv.lock` (one `.venv`). Real JS dependencies live in `package.json` + `pnpm-lock.yaml`. The uv workspace lists its members explicitly, because `apps/` and `packages/` also hold TS members.

Dependencies flow one way: `apps → packages`, `domain → db → core`, `tasks → db → core`, and `@securefabric/client → api` (codegen only). Apps never import each other.

## The control plane: a backend shaped like the dash

The dash shows one team's **workspace**: members, and **environments** (dev, prod, …), each holding **API keys**, **webhooks**, **variables**, **integrations** (a provider enabled with its models and sync schedule), **connections** (one customer's account at a vendor, with health, record counts and **sync jobs**) and **operations** (the logs). The backend models exactly that.

| Layer | Where | What |
|---|---|---|
| Tables | `db/migrations/0002_control_plane.sql` | schema `fabric`: one row per entity above, plus `worker_heartbeats` |
| Models | `packages/domain/.../models.py` | pydantic, camelCase on the wire, epoch-ms timestamps |
| Reads | `repository.py` | `load_workspace()`: the whole snapshot in a fixed number of queries; 40 jobs per connection, 800 operations per environment |
| Writes | `service.py` | every dash action as one transaction: logs operations, fires webhook events, masks credentials, hashes API keys |
| Seed | `seed.py` | the demo workspace (`make seed`, `make seed ARGS=--reset`); the API also seeds an empty DB on first read |
| HTTP | `apps/api/.../api/v1/*.py` | `/api/v1/workspace`, `/environments/{env}/{keys,webhooks,variables,integrations,connections,connect-sessions,operations}`, `/members`, `/status` |
| UI | `apps/dash/src/lib/store.ts` | same exported actions as before, now typed API calls with optimistic patches and a refetch |

**Syncs are real durable tasks.** "Add connection" and "Sync now" record a `RUNNING` job and spawn `sync-connection` (idempotency key `sync:<job id>`). The worker sleeps durably for the simulated vendor sync, then calls `finish_sync`, which sets counts, health, the job result, the logs and webhook events in one transaction. It is idempotent, so a retry or replay after a crash can't apply it twice. A connection with revoked credentials fails at once, as the vendor would. If the task can't be queued, the job is marked failed rather than left hanging.

**The provider catalog flows the other way.** The dash's `src/lib/catalog.ts` (92 providers, their models, credential fields and write actions) is the source of truth. `make generate` exports it to `packages/domain/.../catalog.json`, which the backend uses to validate models and mask secret credential fields. `check-catalog` (turbo, `make verify`, the hooks) fails if it's stale.

Still client-side: the sandbox *records* (findings, devices…) the in-browser playground and record tables generate, the metrics charts, and the in-browser stand-ins for the unified data API. The control plane is real; the vendor data is simulated.

## End-to-end type safety

This follows Polar's approach: the API's pydantic models are the single source of truth, and the TypeScript side is generated from them.

```
pydantic models ──► FastAPI OpenAPI ──► openapi-typescript ──► packages/client/src/v1.ts ──► apps/dash
 (packages/domain, apps/api,     (securefabric-openapi)      (make generate)          lib/types.ts = schemas[…]
  packages/tasks)                                                                     lib/store.ts = api.POST(…)
```

- **The dash's domain types are the API's.** `apps/dash/src/lib/types.ts` aliases `schemas["Connection"]`, `schemas["Environment"]` and so on, and type-level checks pin the UI's lists (`WEBHOOK_EVENTS`, `KEY_SCOPES`, model keys) to the API's enums. Rename a pydantic field, run `make generate`, and `pnpm typecheck` fails at every place the dash uses it.
- **Stable operation IDs.** Every route's `operationId` is `<tag>:<function>`, e.g. `connections:trigger_sync` (`securefabric_api/openapi.py`). Moving a route doesn't churn the client, and TS can name operations: `RequestBody<"environments:update_environment">`.
- **Typed errors.** Every non-2xx body is the `ErrorResponse` envelope (`{error: {code, message, details?}}`) and the schema declares it (404, 409, 422, 500). `unwrap()` throws `NotFoundResponseError`, `ValidationResponseError` (with `.fieldErrors` for forms), and so on; the store toasts the message.
- **Precise shapes.** Request fields with defaults are optional. Response fields are always required (`json_schema_serialization_defaults_required`). Literals become TS unions, so an exhaustive `Record<StatusLevel, Tone>` stops compiling if the backend adds a level.
- **Drift is impossible to merge.** `v1.ts` is committed. `check-generated` (turbo, CI, the pre-commit hook and the pre-push hook) regenerates it in memory and fails on any difference. In `make dev`, the client watcher regenerates it on every Python save.

```bash
make generate          # regenerate v1.ts and catalog.json
make check-generated   # fail if either is stale
make openapi           # dump openapi.json
```

## Turborepo tasks

| Task | Python members | TS members |
|---|---|---|
| `lint` | `ruff check` + `ruff format --check` | `biome check` (Ultracite preset) |
| `typecheck` | `mypy --strict` | `tsc --noEmit` (`next typegen` first in dash) |
| `test` | `pytest` (integration tests run when `TEST_DATABASE_URL` reaches Postgres) | `vitest` |
| `build` | none | `next build` |
| `check-generated` | none | client vs live FastAPI schema |
| `check-catalog` | none | dash `catalog.ts` vs `packages/domain/.../catalog.json` |
| `dev` | uvicorn `--reload` / watchfiles | `next dev` / client watcher |

Lint, typecheck and test depend on `^transit`, so a change in `packages/core` invalidates its dependents' caches without serialising the run. Filter with `make lint F=dash` or `pnpm turbo run test --filter=api...`.

## Git hooks (husky)

`make hooks` (also run by `pnpm install` through `prepare`) installs:

- **pre-commit**
  - blocks direct commits to `main` (the very first commit is allowed)
  - runs Ultracite fix on staged TS/JSON/CSS/YAML and restages the fixes; files that are only partly staged are left for you to review
  - runs the `.pre-commit-config.yaml` hooks on staged files through `uv run`: `uv lock --check`, ruff check/format, mypy, whitespace, YAML/TOML, private-key detection
  - runs `check-generated` when staged changes touch API, domain or task models, or `v1.ts`
  - runs `check-catalog` when staged changes touch the dash catalog or `catalog.json`
- **commit-msg**: commitlint with Conventional Commits (`feat(dash): …`, `fix(api): …`).
- **pre-push**: blocks pushes to `main`, then runs `turbo run typecheck check-generated check-catalog` (cached, so usually instant).

## Durable tasks with Absurd

Absurd keeps queues, runs, checkpoints and events in Postgres. There is no broker. A task runs as a series of **steps**. When a step finishes, its result is checkpointed. On a retry, or after a durable sleep or an event wait, the task replays from the top, and completed steps return their cached result instead of running again.

Every task is declared once, as a `TaskSpec` in `packages/tasks`:

```python
SYNC_CONNECTION = TaskSpec(
    name="sync-connection",
    queue=Queue.DEFAULT,
    params_model=SyncConnectionParams,  # validated before spawning
    result_model=SyncConnectionResult,  # validated when the handler returns
    max_attempts=3,
    retry_strategy={"kind": "exponential", "base_seconds": 1, "factor": 2, "max_seconds": 30},
)
```

The API spawns it after the job is recorded (`apps/api/.../api/v1/connections.py`):

```python
await SYNC_CONNECTION.spawn(absurd, params, idempotency_key=f"sync:{job_id}")
```

The worker's handler (`apps/worker/.../handlers/connections.py`):

```python
await ctx.sleep_for("vendor-sync", params.duration_seconds)  # survives restarts
outcome = await ctx.step("finish", finish)                   # checkpointed; finish_sync is idempotent too
```

`provision-tenant` (spawned from the dash's Workflows page) is the other example.

**Adding a task:**

1. Define the params and result models and a `TaskSpec` in `packages/tasks/src/securefabric_tasks/contracts.py`.
2. Write the handler in a new module under `apps/worker/src/securefabric_worker/handlers/`, exposing `register(client, pool)`.
3. Add that module to `_MODULES` in `handlers/__init__.py`.
4. If it should be triggered over HTTP, add a route in `apps/api` that calls `SPEC.spawn(...)`.

**Rules for handlers:**
- Put side effects inside `ctx.step(...)`, and make each step idempotent.
- Code outside steps re-runs on every replay, so keep it deterministic.
- Step return values must be JSON-serializable.

**Operating Absurd** (`absurdctl` and `psql` run in Docker; you don't need them installed):

```bash
make queues                 # list queues
make tasks q=default        # list tasks
make task id=<uuid>         # one task with its runs and checkpoints
make absurdctl ARGS="retry-task --help"
make absurd-cleanup         # apply retention now (the worker sets cleanup_ttl=30 days)
```

## Configuration

Settings are pydantic-settings classes. Each service reads its own prefix, so variable names never collide:

| Prefix | Class | Where |
|---|---|---|
| `DATABASE_*` | `DatabaseSettings` | packages/db |
| `ABSURD_*` | `AbsurdSettings` | packages/tasks |
| `API_*` | `ApiSettings` | apps/api (`API_CORS_ORIGINS` must include the dash's origin) |
| `WORKER_*` | `WorkerSettings` | apps/worker |
| `NEXT_PUBLIC_API_URL` | `lib/api.ts` | apps/dash (`apps/dash/.env.local`; defaults to `http://localhost:8000`) |

`.env.example` lists every variable. Real environment variables take precedence over `.env`.

## Database migrations

`securefabric-migrate` (`make db-migrate`) applies `db/migrations/*.sql` in lexical order. Each file runs in its own transaction, and an advisory lock keeps concurrent replicas from applying the same migration twice. It also stores a checksum per file and refuses to run if an already-applied file has been edited. In Compose, a one-shot `migrate` service runs it before `api` and `worker` start.

```bash
make db-new-migration name=add_users   # creates a timestamped file
make db-status                         # (make status shows this too)
make seed ARGS=--reset                 # wipe and re-seed the demo workspace
```

To upgrade Absurd, generate the upgrade SQL and add it as a new migration:

```bash
uvx absurdctl migrate --from 0.5.1 --to <new> --dump-sql > db/migrations/<ts>_absurd_<new>.sql
```

## Testing

```bash
make test               # every package via turbo (Python unit + vitest); integration tests skip without Postgres
make test-integration   # starts Postgres, runs integration tests against real Absurd
make test-all           # everything, with TEST_DATABASE_URL set, bypassing the turbo cache
make test-api ARGS="-k status -x"   # one Python package, raw pytest args
make test-dash          # vitest in apps/dash
make cov                # Python coverage → htmlcov/
make stack-test         # Python suite inside the dev container
```

Integration tests are marked `@pytest.mark.integration`. They use `TEST_DATABASE_URL`, which defaults to `securefabric_test` on localhost and is created automatically. If that database can't be reached, they skip. They never fall back to `DATABASE_URL`, so tests can't touch your dev data. They cover the seed, the sync lifecycle (API → Absurd → real worker handler), the dash's API flow and the status endpoint.

## Docker

- **`Dockerfile`** builds the Python apps. Pick one with `--build-arg APP=api|worker` (`make images`). It has two targets:
  - `runtime`: slim image, non-root user (uid 10001). Third-party deps go in their own layer, cached until `uv.lock` changes. Workspace packages are installed non-editable.
  - `dev`: every package installed editable into `/opt/venv`. Compose bind-mounts the repo over `/app`, so code edits apply without a rebuild.
  - `.dockerignore` excludes the JS half of the repo, so dash changes never bust the image cache.
- **`make up`** starts the production-like stack. **`make stack`** starts the hot-reload stack. After changing Python dependencies, run `make stack-build`.
- **Habitat** and **absurdctl** sit behind the `tools` profile in `compose.yaml`. Habitat is on by default in the dev stack.

## Quality

`make verify` is what CI runs:

- both lockfiles are up to date
- `turbo run lint typecheck test check-generated check-catalog check-tokens`: ruff (with bandit, bugbear, FastAPI and async rules) and Biome, `mypy --strict` with the pydantic plugin and `tsc`, pytest and vitest, client drift, catalog drift, and design-token drift
- `ultracite check`

CI also builds the dash and both runtime images, and lints commit messages on PRs. It caches `.turbo/cache`, so unchanged packages are skipped.
