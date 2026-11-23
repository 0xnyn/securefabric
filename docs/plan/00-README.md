# SecureFabric platform plan

_Written 2026-11-23. Scope: the whole platform, proven end to end by one real connector (GitHub Advanced Security) and one synthetic one (SANDBOX)._

## What this plan is

A build plan for the unified security data platform described in `research/platform-requirements.md` (214 requirements) and `research/vuln-appsec-reference.md`. It is scoped so that when it is finished:

1. GitHub Advanced Security is covered completely: code scanning, secret scanning and Dependabot alerts, repositories and branches, on github.com, GHE.com and GitHub Enterprise Server, read and write-back.
2. Every platform capability a later connector will need already exists and is tested. Adding Tenable, Defender or Qualys afterwards means writing a manifest, a stream module and fixtures, with no platform work.

Point 2 is the hard one, because GitHub does not exercise everything. It never needs OAuth2 refresh tokens, async vendor exports, API-key auth, offset pagination or retention-bounded schedules. The plan closes that gap with a second first-party connector, **SANDBOX**: a deterministic synthetic vendor that runs inside the worker and exercises exactly the primitives GitHub does not. SANDBOX also gives customers sandbox connections (TEN-13) and gives us an end-to-end test target with no network. Together the two connectors are the platform's conformance suite.

## Parts

| Part | File | Contents |
|---|---|---|
| 1 | `01-architecture.md` | Processes, packages, trust boundaries, what happens to the existing repo, decision log |
| 2 | `02-data-model.md` | Every table, key, index and partitioning choice, plus the canonical Resource and Finding shapes |
| 3 | `03-tenancy-connections-vault.md` | Accounts, environments, WorkOS, API keys, vault, connection lifecycle, connect flow, health |
| 4 | `04-sync-engine.md` | Schedules, jobs, admission on top of Absurd, checkpoints, rate budgets, the record write path, deletion detection |
| 5 | `05-connector-sdk.md` | Manifest, stream interface, HTTP client, fixtures, conformance tests, the SANDBOX connector |
| 6 | `06-github-connector.md` | The GitHub App, permissions, streams, field mappings, incremental strategy, webhooks, GHES, write-back |
| 7 | `07-public-api-and-events.md` | Endpoints, pagination, filters, errors, idempotency, outbox, outbound webhooks |
| 8 | `08-dashboard-and-connect-ui.md` | How `apps/dash` moves from the mock to the real API, and the hosted connect flow |
| 9 | `09-operations-security-quality.md` | Observability, security controls, test strategy, deployment, retention |
| 10 | `10-delivery-plan.md` | Milestones with exit criteria, work lanes, requirement traceability, deferred items, spikes |

Read parts 1 and 2 first. Parts 3 to 9 can be read in any order. Part 10 is the execution order.

## The shape in one page

```
 customer backend ──X-API-KEY──►┐                          ┌──► GitHub REST (github.com / GHE.com / GHES)
 dashboard (WorkOS session) ───►│  api (FastAPI)           │
 connect UI (session token) ───►│   • cannot open vault    │
 GitHub webhooks ──signature───►│   • writes outbox        │
                                └──────────┬───────────────┘
                                           │ Postgres (one database, five schemas, RLS by environment)
                ┌──────────────────────────┼─────────────────────────────┐
                │ control                  │ sync                        │ data / events / obs
                │ accounts, environments   │ schedules, jobs, runs       │ resources, findings
                │ orgs, integrations       │ checkpoints, rate buckets   │ outbox, deliveries
                │ connections, vault       │ ingress deliveries          │ operations, audit
                └──────────────────────────┼─────────────────────────────┘
                                           │ Absurd queues (durable leases)
                 ┌──────────────┬──────────┴──────┬────────────────┐
                 │ scheduler    │ sync workers    │ control workers │ delivery workers
                 │ admission,   │ run connector   │ verify, refresh │ outbound webhooks
                 │ fairness     │ streams         │ lifecycle       │
                 └──────────────┴─────────────────┴────────────────┘
                                 only these open the vault
```

## The decisions that shape everything else

Full reasoning is in part 1. The short version:

| # | Decision | Why |
|---|---|---|
| PD-1 | Keep Absurd as the durable execution layer and add our own admission layer above it. | Absurd gives leases, crash recovery, cancellation and idempotent spawn, but claims strictly FIFO. Priority, fairness and concurrency caps (SYNC-08, 11, 12) live in our `stream_run` table and a scheduler that decides what enters Absurd. |
| PD-2 | Two reference connectors, GITHUB and SANDBOX. | One real vendor for truth, one synthetic vendor for breadth. No platform primitive ships untested. |
| PD-3 | Tenancy is Account → Environment → Organization → Connection, with an Integration (a connector enabled and configured in one environment) between connector and connection. | Matches Leen and the requirements, keeps the dashboard's existing "integrations" concept, and gives vendor app registrations and per-environment defaults a home. |
| PD-4 | Vendor credentials are sealed to a per-environment public key. Only worker processes hold the private key. | An API-tier compromise cannot leak vendor credentials. This replaces Nango-style task-scoped tokens (SEC-04), which only exist because Nango's runners call back into its API. |
| PD-5 | Canonical typed tables, hash-partitioned by connection, with a per-row `seen_gen` for sweep deletion. | Normalise at ingest (D4). `seen_gen` replaces Nango's separate `records_seen` table, because we already touch each row to record `last_seen_at`. |
| PD-6 | `updated_at` is assigned under the per-stream write lock and forced monotonic. | Makes `(updated_at, id)` a commit-ordered cursor per connection, so incremental readers never skip a change (CDC-01). |
| PD-7 | Replace the `fabric.*` mock schema and the mock `domain` package instead of migrating them. | Nothing is committed or deployed, the mock is single-workspace with plaintext secrets, and its shape follows the UI rather than the requirements. |
| PD-8 | One API surface (`/v1`) for customers and the dashboard, with two authenticators: API key and WorkOS session. | The dashboard dogfoods the public API, and every dashboard feature is automatically available to customers. |
| PD-9 | Wire-compatible with Leen V2 field names and enums. Our improvements are additive. | D10 in the requirements. Lets a Leen customer switch base URL. |
| PD-10 | The shared GitHub App is the default, and a customer-owned app is supported per environment. | Shared is what makes one-click install work. Customer-owned is required for GHES anyway, so the model supports both from the start. |

## Status of the inputs

- Requirements, the appsec reference, the rest of the research folder, and the current repository were all read for this plan.
- The GitHub API facts were checked against docs.github.com by a research pass. Items that pass could not confirm are listed as spikes in part 10, section 6, and nothing in the design depends on an unconfirmed fact without a stated fallback.
- The working tree was being edited while this plan was written (`packages/domain`, `packages/tasks`, `apps/worker`). The plan adds files under `docs/plan/` only.
