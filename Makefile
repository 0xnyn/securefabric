# =============================================================================
# SecureFabric monorepo: run `make` (or `make help`) to list every target.
#
# One Turborepo over two toolchains:
#   Python (uv workspace):  apps/api, apps/worker, packages/{core,db,tasks}
#   TypeScript (pnpm):      apps/dash, packages/{client,ui,tokens,config}
#
# Targets are thin wrappers over turbo/pnpm/uv, so nothing here is the only
# way to do a thing. `pnpm <script>` at the root runs the same pipelines.
# =============================================================================

SHELL         := /usr/bin/env bash
.SHELLFLAGS   := -eu -o pipefail -c
.DEFAULT_GOAL := help
MAKEFLAGS     += --no-print-directory

UV            ?= uv
PNPM          ?= pnpm
RUN           := $(UV) run
TURBO         := $(PNPM) exec turbo run
COMPOSE       ?= docker compose
DEV_COMPOSE   := $(COMPOSE) -f compose.yaml -f compose.dev.yaml
TOOLS_COMPOSE := $(COMPOSE) --profile tools

APPS          := api worker
PACKAGES      := core db tasks
TEST_DB_URL   ?= postgresql://securefabric:securefabric@localhost:5432/securefabric_test

# Pass extra args to some targets, e.g.  make test-api ARGS="-k tenants -x"
ARGS          ?=
# Service selector for logs/shell/restart, e.g.  make stack-logs s=worker
s             ?=
# Turbo filter, e.g.  make lint F=dash   or   make test F=@securefabric/tasks
F             ?=
TURBO_FILTER  := $(if $(F),--filter=$(F),)

# Pretty output
C_RESET := \033[0m
C_BOLD  := \033[1m
C_CYAN  := \033[36m
C_GREEN := \033[32m
C_DIM   := \033[2m

##@ Help

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\n$(C_BOLD)Usage:$(C_RESET) make $(C_CYAN)<target>$(C_RESET) [ARGS=...] [F=<turbo filter>] [s=<service>]\n"} \
		/^[a-zA-Z0-9_.-]+:.*?##/ { printf "  $(C_CYAN)%-22s$(C_RESET) %s\n", $$1, $$2 } \
		/^##@/ { printf "\n$(C_BOLD)%s$(C_RESET)\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@echo

##@ Status

.PHONY: status
status: ## What state is everything in? Tools, deps, services, API/dash/worker, workspace, drift, git
	@$(RUN) --frozen python scripts/status.py $(ARGS)

.PHONY: status-fast
status-fast: ## The status report without the (slower) generated-code drift checks
	@$(RUN) --frozen python scripts/status.py --fast $(ARGS)

.PHONY: status-json
status-json: ## The status report as JSON (for scripts and CI)
	@$(RUN) --frozen python scripts/status.py --json $(ARGS)

.PHONY: status-api
status-api: ## Ask the running API for its status (GET /v1/status; set API_KEY for more)
	@curl -fsS $${API_KEY:+-H "Authorization: Bearer $${API_KEY}"} http://localhost:$${API_PORT:-8000}/v1/status | $(RUN) python -m json.tool

##@ Setup

.PHONY: bootstrap
bootstrap: doctor env install hooks ## One-shot setup: check tools, create .env, install deps + git hooks
	@printf "$(C_GREEN)✔ Ready.$(C_RESET) Next: $(C_CYAN)make dev$(C_RESET) (postgres in Docker; api, worker, dash on the host)\n"

.PHONY: doctor
doctor: ## Check required tooling is installed
	@for bin in uv node pnpm docker git; do \
		if command -v $$bin >/dev/null 2>&1; then printf "  $(C_GREEN)✔$(C_RESET) %-8s %s\n" $$bin "$$($$bin --version 2>/dev/null | head -1)"; \
		else printf "  ✘ %-8s missing\n" $$bin; missing=1; fi; \
	done; \
	if docker info >/dev/null 2>&1; then printf "  $(C_GREEN)✔$(C_RESET) docker daemon running\n"; else printf "  ✘ docker daemon not reachable\n"; fi; \
	test -z "$${missing:-}"

.PHONY: env
env: ## Create .env from .env.example (never overwrites)
	@if [ -f .env ]; then echo ".env already exists (left untouched)"; else cp .env.example .env && echo "created .env"; fi

.PHONY: install
install: ## Install everything from the lockfiles: Python (uv) + JS (pnpm)
	$(UV) sync --frozen --all-packages
	$(PNPM) install --frozen-lockfile

.PHONY: sync
sync: ## Sync deps, updating lockfiles if pyproject/package.json files changed
	$(UV) sync --all-packages
	$(PNPM) install

.PHONY: lock
lock: ## Re-resolve uv.lock and pnpm-lock.yaml without upgrading
	$(UV) lock
	$(PNPM) install --lockfile-only

.PHONY: lock-check
lock-check: ## Fail if a lockfile is out of date
	$(UV) lock --check
	$(PNPM) install --frozen-lockfile --lockfile-only

.PHONY: upgrade
upgrade: ## Upgrade all dependencies to the latest allowed versions
	$(UV) lock --upgrade
	$(UV) sync --all-packages
	$(PNPM) update -r

.PHONY: upgrade-pkg
upgrade-pkg: ## Upgrade one Python dependency: make upgrade-pkg p=fastapi
	@test -n "$(p)" || (echo "usage: make upgrade-pkg p=<package>" && exit 1)
	$(UV) lock --upgrade-package $(p)
	$(UV) sync --all-packages

.PHONY: add
add: ## Add a Python dep: make add to=api p="httpx2>=2"  (to=dev for the dev group)
	@test -n "$(to)" -a -n "$(p)" || (echo 'usage: make add to=<api|worker|core|db|tasks|dev> p="<pkg>"' && exit 1)
	@if [ "$(to)" = "dev" ]; then $(UV) add --dev $(p); else $(UV) add --package securefabric-$(to) $(p); fi

.PHONY: add-js
add-js: ## Add a JS dep: make add-js to=dash p=zod  (to=<package name>, D=1 for dev)
	@test -n "$(to)" -a -n "$(p)" || (echo 'usage: make add-js to=<dash|@securefabric/ui|...> p="<pkg>" [D=1]' && exit 1)
	$(PNPM) add $(if $(D),-D,) --filter $(to) $(p)

.PHONY: tree
tree: ## Show the Python dependency tree
	$(UV) tree $(ARGS)

.PHONY: hooks
hooks: ## Install git hooks (husky: pre-commit, commit-msg, pre-push)
	@if [ -d .git ]; then $(PNPM) exec husky && echo "hooks installed (.husky/)"; else echo "not a git repo; skipping hooks"; fi

##@ Quality (Turborepo: cached, only re-runs what changed)

.PHONY: verify
verify: lock-check ## Everything CI runs: lockfiles, lint, types, tests, client + token drift
	$(TURBO) lint typecheck test check-generated check-tokens $(TURBO_FILTER)
	$(PNPM) exec ultracite check

.PHONY: check
check: verify ## Alias for verify

.PHONY: lint
lint: ## Lint every package (ruff for Python, Biome for TS): make lint [F=dash]
	$(TURBO) lint $(TURBO_FILTER)

.PHONY: typecheck
typecheck: ## Type-check every package (mypy strict + tsc): make typecheck [F=api]
	$(TURBO) typecheck $(TURBO_FILTER)
	$(RUN) mypy conftest.py scripts

.PHONY: fmt
fmt: ## Format everything (ruff + import sorting, Ultracite/Biome)
	$(RUN) ruff check --select I --fix .
	$(RUN) ruff format .
	$(PNPM) exec ultracite fix

.PHONY: fmt-check
fmt-check: ## Check formatting without writing
	$(RUN) ruff format --check .
	$(PNPM) exec ultracite check

.PHONY: fix
fix: ## Auto-fix lint + formatting everywhere
	$(RUN) ruff check --fix .
	$(RUN) ruff format .
	$(PNPM) exec ultracite fix

.PHONY: pre-commit
pre-commit: ## Run the Python/hygiene pre-commit hooks on every file
	$(RUN) pre-commit run --all-files

.PHONY: lint-commits
lint-commits: ## Check commit messages on this branch follow Conventional Commits
	$(PNPM) exec commitlint --from origin/main --to HEAD --verbose

##@ End-to-end types (FastAPI → OpenAPI → @securefabric/client)

.PHONY: generate
generate: ## Regenerate the TS client (v1.ts) from the API's OpenAPI document
	$(PNPM) run generate

.PHONY: check-generated
check-generated: ## Fail if the generated TS client is stale
	$(TURBO) check-generated

.PHONY: watch-client
watch-client: ## Regenerate the client whenever API/task models change
	$(PNPM) -F @securefabric/client dev

.PHONY: openapi
openapi: ## Export the OpenAPI schema to openapi.json
	$(RUN) securefabric-openapi > openapi.json
	@echo "wrote openapi.json"

##@ Tests

.PHONY: test
test: ## Run every package's tests via turbo (integration tests skip without Postgres)
	$(TURBO) test $(TURBO_FILTER)

.PHONY: test-all
test-all: ## Run every test; integration ones need `make db-up`
	TEST_DATABASE_URL=$(TEST_DB_URL) $(TURBO) test --force

.PHONY: test-integration
test-integration: db-up ## Start Postgres and run integration tests against it
	TEST_DATABASE_URL=$(TEST_DB_URL) $(RUN) pytest -m integration $(ARGS)

.PHONY: test-api test-worker test-core test-db test-tasks test-schema test-cdk test-connectors test-domain
test-api: ## Run tests for apps/api only (pytest ARGS)
	$(RUN) pytest apps/api $(ARGS)
test-worker: ## Run tests for apps/worker only
	$(RUN) pytest apps/worker $(ARGS)
test-core: ## Run tests for packages/core only
	$(RUN) pytest packages/core $(ARGS)
test-db: ## Run tests for packages/db only (RLS guarantees)
	$(RUN) pytest packages/db $(ARGS)
test-tasks: ## Run tests for packages/tasks only
	$(RUN) pytest packages/tasks $(ARGS)
test-schema: ## Run tests for packages/schema only
	$(RUN) pytest packages/schema $(ARGS)
test-cdk: ## Run tests for packages/cdk only
	$(RUN) pytest packages/cdk $(ARGS)
test-connectors: ## Connector conformance, golden output, fixtures (SANDBOX, GitHub)
	$(RUN) pytest packages/connectors $(ARGS)
test-domain: ## Run tests for packages/domain only (write path, engine, maintenance)
	$(RUN) pytest packages/domain $(ARGS)

.PHONY: test-dash test-client
test-dash: ## Run tests for apps/dash (vitest)
	$(PNPM) -F dash test
test-client: ## Run tests for packages/client (vitest)
	$(PNPM) -F @securefabric/client test

.PHONY: cov
cov: ## Run Python tests with coverage (terminal + htmlcov/)
	TEST_DATABASE_URL=$(TEST_DB_URL) $(RUN) pytest --cov --cov-report=term-missing --cov-report=html $(ARGS)
	@echo "open htmlcov/index.html"

.PHONY: test-watch
test-watch: ## Re-run Python unit tests on file changes
	$(RUN) watchfiles --filter python "uv run pytest -m 'not integration' -q $(ARGS)" apps packages

##@ Develop (host processes, hot reload; Postgres in Docker)

.PHONY: dev-preflight
dev-preflight: ## Check the dash and API agree on sign-in (WorkOS) before starting
	@$(RUN) --frozen python scripts/check_dev_auth.py

.PHONY: dev
dev: dev-preflight db-up db-migrate ## Postgres + api + worker + dash + client watcher, all hot-reloading
	@printf "API → http://localhost:8000/docs   Dash → http://localhost:3000\n"
	$(PNPM) run dev

.PHONY: dev-api
dev-api: ## Run only the API with hot reload on http://localhost:8000
	$(PNPM) run dev:api

.PHONY: dev-worker
dev-worker: ## Run only the worker, restarting on code changes
	$(PNPM) run dev:worker

.PHONY: dev-dash
dev-dash: dev-preflight ## Run only the dash (+ client watcher) on http://localhost:3000
	$(PNPM) run dev:dash

.PHONY: build
build: ## Build every buildable package (Next.js production build of apps/dash)
	$(TURBO) build $(TURBO_FILTER)

.PHONY: start-dash
start-dash: ## Serve the production build of apps/dash on http://localhost:3000
	$(PNPM) -F dash start

.PHONY: shell
shell: ## Python REPL with the workspace importable
	$(RUN) python

##@ Database (Postgres in Docker)

.PHONY: db-up
db-up: ## Start Postgres and MinIO (raw page archive) and wait until healthy
	$(COMPOSE) up -d --wait postgres minio

.PHONY: db-down
db-down: ## Stop Postgres (data kept)
	$(COMPOSE) stop postgres

.PHONY: db-migrate
db-migrate: ## Apply pending SQL migrations (incl. Absurd schema) to DATABASE_URL
	$(RUN) securefabric-migrate $(ARGS)

.PHONY: db-status
db-status: ## Show applied/pending migrations
	$(RUN) securefabric-migrate --status

.PHONY: seed
seed: ## Bootstrap the platform, then seed a demo account, environment and SANDBOX connection
	$(RUN) securefabric-admin bootstrap
	$(RUN) securefabric-admin seed $(ARGS)

.PHONY: db-new-migration
db-new-migration: ## Create a new migration file: make db-new-migration name=add_users
	@test -n "$(name)" || (echo "usage: make db-new-migration name=<snake_case>" && exit 1)
	@f="db/migrations/$$(date -u +%Y%m%d%H%M%S)_$(name).sql"; \
	printf -- "-- %s\n-- Forward-only. Never edit after it has been applied anywhere.\n\n" "$(name)" > $$f; \
	echo "created $$f"

.PHONY: db-shell
db-shell: ## Open psql inside the Postgres container
	$(COMPOSE) exec postgres psql -U securefabric -d securefabric

.PHONY: db-reset
db-reset: ## ⚠ Destroy the Postgres volume, recreate, and migrate
	@read -r -p "This deletes ALL local Postgres data. Continue? [y/N] " ans && [ "$${ans:-N}" = "y" ]
	$(COMPOSE) rm -sfv postgres
	docker volume rm -f securefabric_pgdata
	$(MAKE) db-up db-migrate

.PHONY: db-dump
db-dump: ## Dump the dev database to backups/<timestamp>.sql.gz
	@mkdir -p backups
	$(COMPOSE) exec -T postgres pg_dump -U securefabric securefabric | gzip > backups/$$(date -u +%Y%m%d%H%M%S).sql.gz
	@ls -1t backups | head -1

##@ Absurd (durable tasks)

.PHONY: absurdctl
absurdctl: ## Run absurdctl in Docker: make absurdctl ARGS="list-tasks --queue control"
	$(TOOLS_COMPOSE) run --rm absurdctl $(ARGS)

.PHONY: queues
queues: ## List Absurd queues
	@$(MAKE) absurdctl ARGS="list-queues"

.PHONY: queue-create
queue-create: ## Create a queue: make queue-create q=emails
	@test -n "$(q)" || (echo "usage: make queue-create q=<name>" && exit 1)
	@$(MAKE) absurdctl ARGS="create-queue $(q)"

.PHONY: tasks
tasks: ## List tasks in a queue: make tasks [q=control|sync_interactive|sync_bulk|delivery|maintenance]
	@$(MAKE) absurdctl ARGS="list-tasks --queue $(or $(q),control)"

.PHONY: task
task: ## Dump one task with its runs + checkpoints: make task id=<task_id>
	@test -n "$(id)" || (echo "usage: make task id=<task_id>" && exit 1)
	@$(MAKE) absurdctl ARGS="dump-task --task-id=$(id)"

.PHONY: absurd-cleanup
absurd-cleanup: ## Apply each queue's retention policy now (absurd.cleanup_all_queues)
	$(COMPOSE) exec -T postgres psql -U securefabric -d securefabric -c "select * from absurd.cleanup_all_queues();"

.PHONY: github-seed
github-seed: ## Seed the GitHub test org (idempotent); ARGS=--check for the preflight only
	@env $$(grep -E '^(GITHUB_SEED_TOKEN|GITHUB_TEST_ORG)=' .env | xargs) $(RUN) python tools/github_seed.py $(ARGS)

.PHONY: generate-python-client
generate-python-client: ## Regenerate the Python client (clients/python) from the OpenAPI document
	$(RUN) python scripts/gen_python_client.py

.PHONY: drill-restore
drill-restore: ## Backup restore drill: dump, restore into a scratch DB, verify, drop it
	$(RUN) python tools/drills/restore_drill.py

.PHONY: bench bench-absurd bench-ingest bench-api bench-admission bench-outbox bench-scale-out
bench: bench-ingest bench-api bench-admission bench-outbox bench-absurd ## Run the benchmark gates (plan part 10, section 8) on the test DB
bench-absurd: ## Absurd throughput, claim latency and cleanup cost (test DB): ARGS="--tasks 5000"
	TEST_DATABASE_URL=$(TEST_DB_URL) $(RUN) python tools/bench/absurd_load.py $(ARGS)
bench-ingest: ## Ingest gate: >= 2,000 records/s per worker (NFR-05)
	TEST_DATABASE_URL=$(TEST_DB_URL) $(RUN) python tools/bench/ingest.py $(ARGS)
bench-api: ## Data API gates over HTTP (NFR-04): ARGS="--findings 1000000"
	TEST_DATABASE_URL=$(TEST_DB_URL) $(RUN) python tools/bench/api_latency.py $(ARGS)
bench-admission: ## Admission gate: 200 runs/s, lag < 5 s (ARGS=--uncapped to lift caps)
	TEST_DATABASE_URL=$(TEST_DB_URL) $(RUN) python tools/bench/admission.py --uncapped $(ARGS)
bench-outbox: ## Outbox gate: 99% of events delivered within 60 s (NFR-03)
	TEST_DATABASE_URL=$(TEST_DB_URL) $(RUN) python tools/bench/outbox.py $(ARGS)
bench-scale-out: ## Scale-out gate: 2 sync workers ~ 2x one (NFR-07)
	TEST_DATABASE_URL=$(TEST_DB_URL) $(RUN) python tools/bench/scale_out.py $(ARGS)

.PHONY: docs-connectors
docs-connectors: ## Regenerate docs/connectors/*.md (and capabilities.json) from each connector
	@for d in packages/connectors/src/securefabric_connectors/*/; do \
		if [ -f "$$d/manifest.yaml" ]; then \
			$(RUN) securefabric-cdk capabilities "$$d" >/dev/null && $(RUN) securefabric-cdk docs "$$d"; \
		fi; \
	done

.PHONY: demo
demo: ## Trigger an on-demand sync and follow the job: make demo API_KEY=sfk_... CONNECTION=<id>
	@$(RUN) python scripts/demo.py

.PHONY: habitat
habitat: ## Start the Habitat dashboard on http://localhost:7890
	$(TOOLS_COMPOSE) up -d --wait habitat
	@echo "Habitat → http://localhost:7890"

##@ Docker: dev stack (api + worker in containers, hot reload, Habitat)

.PHONY: stack
stack: ## Start postgres, api, worker, Habitat in Docker (foreground); pair with `make dev-dash`
	$(DEV_COMPOSE) up --build --remove-orphans

.PHONY: stack-up
stack-up: ## Same as `stack` but detached
	$(DEV_COMPOSE) up --build --remove-orphans -d --wait
	@printf "API      → http://localhost:8000/docs\nHabitat  → http://localhost:7890\nDash     → make dev-dash\n"

.PHONY: stack-down
stack-down: ## Stop the dev stack (data kept)
	$(DEV_COMPOSE) down --remove-orphans

.PHONY: stack-build
stack-build: ## Rebuild the dev image (after Python dependency changes)
	$(DEV_COMPOSE) build $(ARGS)

.PHONY: stack-logs
stack-logs: ## Tail dev stack logs: make stack-logs [s=api]
	$(DEV_COMPOSE) logs -f --tail=200 $(s)

.PHONY: stack-ps
stack-ps: ## Show dev stack status
	$(DEV_COMPOSE) ps

.PHONY: stack-restart
stack-restart: ## Restart dev service(s): make stack-restart [s=worker]
	$(DEV_COMPOSE) restart $(s)

.PHONY: stack-shell
stack-shell: ## Shell into a dev container: make stack-shell [s=api]
	$(DEV_COMPOSE) exec $(or $(s),api) bash

.PHONY: stack-test
stack-test: ## Run the Python test suite inside the dev container
	$(DEV_COMPOSE) run --rm -e TEST_DATABASE_URL=postgresql://securefabric:securefabric@postgres:5432/securefabric_test api pytest $(ARGS)

##@ Docker: production-like stack

.PHONY: images
images: ## Build runtime images for all Python apps
	@for app in $(APPS); do \
		echo "→ securefabric-$$app:local"; \
		docker build --build-arg APP=$$app --target runtime -t securefabric-$$app:local . ; \
	done

.PHONY: image-api image-worker
image-api: ## Build the API runtime image
	docker build --build-arg APP=api --target runtime -t securefabric-api:local .
image-worker: ## Build the worker runtime image
	docker build --build-arg APP=worker --target runtime -t securefabric-worker:local .

.PHONY: up
up: ## Start the production-like stack (detached, waits for health)
	$(COMPOSE) up --build -d --wait --remove-orphans
	@echo "API → http://localhost:8000/docs"

.PHONY: down
down: ## Stop the production-like stack (data kept)
	$(COMPOSE) --profile tools down --remove-orphans

.PHONY: logs
logs: ## Tail logs: make logs [s=worker]
	$(COMPOSE) logs -f --tail=200 $(s)

.PHONY: ps
ps: ## Show stack status
	$(COMPOSE) --profile tools ps

.PHONY: scale-worker
scale-worker: ## Scale workers: make scale-worker n=4
	$(COMPOSE) up -d --no-recreate --scale worker=$(or $(n),2) worker

.PHONY: nuke
nuke: ## ⚠ Stop everything and delete volumes + local images
	@read -r -p "Remove containers, volumes and local images? [y/N] " ans && [ "$${ans:-N}" = "y" ]
	$(DEV_COMPOSE) --profile tools down -v --remove-orphans --rmi local

##@ Housekeeping

.PHONY: clean
clean: ## Remove caches, build artefacts and coverage output
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache -o -name .turbo -o -name .next \) -not -path "./.venv/*" -not -path "*/node_modules/*" -prune -exec rm -rf {} +
	rm -rf htmlcov .coverage .coverage.* coverage.xml dist build openapi.json

.PHONY: clean-all
clean-all: clean ## clean + remove .venv and every node_modules
	rm -rf .venv
	find . -name node_modules -type d -prune -exec rm -rf {} +

.PHONY: info
info: ## Show workspace members and versions
	@$(UV) --version
	@$(RUN) python --version
	@printf "node %s, pnpm %s\n" "$$(node --version)" "$$($(PNPM) --version)"
	@printf "$(C_BOLD)Python (uv)$(C_RESET)\n"
	@for p in $(APPS:%=apps/%) $(PACKAGES:%=packages/%); do \
		printf "  %-18s %s\n" "$$p" "$$(grep -m1 '^version' $$p/pyproject.toml | cut -d'"' -f2)"; \
	done
	@printf "$(C_BOLD)Turborepo graph$(C_RESET)\n"
	@$(PNPM) -r ls --depth -1 2>/dev/null | grep -E '^\S' | sed 's/^/  /'
