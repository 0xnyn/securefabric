# SecureFabric architecture

The as-built architecture of SecureFabric: what each subsystem does, why it is shaped the way it is, which guarantees it makes, and which tests prove them. It describes the code on `chore/initial-scaffold` as of 2026-11-24.

## How this relates to the other docs

| Document | Answers | Written |
|---|---|---|
| [`docs/plan/`](../plan/00-README.md) | What we intended to build and why: requirements traceability, decisions PD-1 to PD-15, milestones and exit criteria | Before the build (2026-11-23) |
| **`docs/architecture/` (this series)** | What exists now and how it works: mechanisms, invariants and their tests, failure modes, extension points, known gaps | After the build |
| [`progress.md`](../../progress.md) | What was validated and how (test, live call, benchmark), spikes, deviations, build log | During the build |
| [Runbooks](../runbooks/README.md), [guides](../guides/), [connector pages](../connectors/) | How to operate it, integrate with it, and what each connector emits | Alongside the code |

Where the plan and the code disagree, the code wins, and this series says so. Deviations are collected in [Part 10](10-decisions-status-and-roadmap.md).

## Parts

| Part | Read it for |
|---|---|
| [1. System context](01-system-context.md) | Actors, processes and roles, package layering, data stores, and the connect / sync / read / react flows end to end. **Start here.** |
| [2. Tenancy, identity and security](02-tenancy-identity-and-security.md) | Account → environment → organization → connection, principals, Postgres roles and RLS, the vault and every key, egress control, redaction, audit, trust boundaries |
| [3. Data model and record store](03-data-model-and-record-store.md) | The five schemas, partitioning, the canonical Leen-compatible models, `apply_batch`, the monotonic clock, sweeps, the raw archive, payload encryption, retention |
| [4. Sync engine](04-sync-engine.md) | Schedules, jobs and runs, the scheduler and admission on top of Absurd, slices, retries and parking, checkpoints, rate budgets, health |
| [5. Connector platform](05-connector-platform.md) | Manifests, the CDK, normalisation, conformance, SANDBOX and GitHub in depth, and a walkthrough for adding a connector |
| [6. Connections and the connect flow](06-connections-and-connect-flow.md) | The connection lifecycle, verification and grants, connect sessions, the GitHub App install, OAuth2, credential rotation |
| [7. Public API and events](07-public-api-and-events.md) | The `/v1` surface and its conventions, the data API, write-back actions, the outbox, outbound webhooks, inbound ingress |
| [8. Dashboard, connect UI and clients](08-dashboard-and-clients.md) | The Next.js app, its auth and proxy, the hosted connect UI, connect-js, and the generated TypeScript and Python clients |
| [9. Operations and reliability](09-operations-and-reliability.md) | Deployment shape, metrics, logs, alerts and runbooks, status, maintenance jobs, the operator console, benchmarks, drills, CI gates |
| [10. Decisions, status and roadmap](10-decisions-status-and-roadmap.md) | The decision log as built, deviations from the plan, what is proven and how, known gaps and risks, and what comes next |

Reading paths:

- **New engineer:** 1 → 2 → 3 → 4, then whichever area you are working in.
- **Writing a connector:** 1 → 5 → 4 (sections on errors, checkpoints and rate budgets) → 3 (the write path).
- **Integrating as a customer engineer:** 1 → 7 → 6 → the [webhooks guide](../guides/webhooks.md).
- **On call:** 9 → the [runbooks](../runbooks/README.md) → 4.
- **Security review:** 2 → 6 → 7 (ingress and signing) → 9 (key rotation).

## Conventions in this series

- Code is referenced by path and symbol (`packages/domain/src/securefabric_domain/records.py`, `apply_batch`), not by line number.
- Requirement ids (`SYNC-08`, `AUTH-06`, `CDC-01` ...) come from the requirements the plan traces, and `PD-n` are the plan's decisions. Both are cited where the code cites them.
- Each part ends with an **invariants** table (guarantee → mechanism → test), **failure modes**, **extending it**, and **known gaps**, so the limits of what is proven are visible next to the claims.
- Diagrams are Mermaid and render on GitHub.

## Glossary

| Term | Meaning |
|---|---|
| Account | The customer company. Owns environments and members. |
| Environment | An isolated tenant inside an account (`dev`, `prod`). The RLS key: every tenant row carries `environment_id`. Has its own vault key pair and API keys. |
| Organization | The customer's own customer (the end user's company). Groups connections. Leen calls the same thing an organization. |
| Connector | Code plus a manifest for one vendor (`GITHUB`, `SANDBOX`). Global and versioned. |
| Integration | One environment's use of a connector: enabled streams, default intervals and options, which vendor app to use. |
| Vendor app | An OAuth or GitHub App registration. The platform's shared app is the default; a customer-owned app is supported per environment. |
| Connection | One organization's authorised link to one vendor account through one integration. Has a lifecycle state and a health code. |
| Stream | One kind of vendor object a connector reads (`dependabot_alerts`, `repositories`). Writes one canonical object type. |
| Grant | Whether a connection's credential can read a stream, recorded by probes at verification: `GRANTED`, `UNAUTHORIZED`, `NOT_ENABLED`, `UNSUPPORTED` or `UNKNOWN`. |
| Job / stream run / slice | A job groups the stream runs of one sync. A stream run is one stream's pass. A slice is one Absurd task executing part of a run, until it finishes, parks or yields. |
| Pass, generation | A full pass reads everything and ends with a sweep; each pass has a generation number stamped on every row it sees. |
| Sweep | Marking rows not seen in a completed full pass as deleted, guarded against partial passes. |
| Admission | The scheduler's step that decides which queued runs enter Absurd, by priority, fairness and caps. |
| Parking | Ending a slice early to wait out a long rate-limit reset without holding a worker. |
| Outbox | `events.outbox_event`, written in the same transaction as the state change it describes; the source for webhooks and `GET /v1/events`. |
| Ingress | Inbound vendor webhooks: verified, stored by delivery id, and turned into targeted refreshes. |
| Vault | Per-environment X25519 key pairs, wrapped by a KEK, used to seal credentials so only workers can open them. |
| SANDBOX | A synthetic, deterministic, in-process vendor that exercises every platform primitive GitHub does not. |
| Leen V2 | The API SecureFabric is wire-compatible with: field names, enums and query parameters. |
