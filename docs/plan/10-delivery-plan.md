# Part 10: Delivery plan

## 1. How the work is ordered

Eleven milestones. Each ends in something demonstrable and has exit criteria that are tests, not opinions. The order follows one rule: build each platform layer against SANDBOX first, where failures can be injected and nothing depends on a vendor, then prove it against GitHub.

```
M0 Foundations ─► M1 Tenancy and catalogue ─► M2 CDK, SANDBOX, record store ─► M3 Sync engine ─┐
                                                                                               ▼
        M6 Events and webhooks ◄── M5 GitHub alerts and data API ◄── M4 Connections, connect flow, first GitHub sync
                 │
                 ▼
        M7 Observability and dashboard ─► M8 Platform breadth ─► M9 GitHub completeness ─► M10 Hardening and launch
```

Sizes are rough estimates in engineer-weeks, made before any of this is built. Re-baseline after M3, when the two hardest pieces (the write path and admission) have real numbers.

## 2. Milestones

### M0: Foundations (about 2 engineer-weeks)
Reset the base so everything after it is built on the real shape.

- Replace `0002_control_plane.sql` with the real schemas, roles and RLS policies. Add `tenant_tx`.
- Create `packages/schema`, `packages/cdk`, `packages/connectors` skeletons and the import-boundary lint.
- `packages/core`: ids (UUIDv5 namespace, UUIDv7), clock, canonical JSON encoder and hash, sealed-box and envelope primitives, `KeyProvider` with the local implementation.
- API: `/v1` prefix, problem+json errors, principal dependency, WorkOS token verification, API key authentication.
- Worker roles and the five queues. Object store in compose.
- Fix the READMEs and the `make` targets that reference things that do not exist.

**Exit.** `make verify` is green. A test with no tenant setting reads zero rows from every tenant table. Hash property tests pass. A user can sign in through WorkOS and call `GET /v1/me`.

### M1: Tenancy and catalogue (about 2)
- Accounts, memberships, environments, API keys with scopes, organizations, with audit events.
- Manifest schema, manifest loader into `control.connector`, catalogue endpoints, integrations and vendor apps.
- Dashboard: sign-in, onboarding, environment switcher, Keys, Catalogue, Integrations and Organizations on real data.

**Exit.** The generated cross-environment isolation suite passes for every endpoint that exists. A key is shown once and a revoked key fails within 60 seconds. The catalogue page renders from a manifest, and `lib/catalog.ts` is deleted.

### M2: CDK, SANDBOX and the record store (about 3)
- Canonical models in `packages/schema`, validated against Leen V2 example payloads.
- CDK: connector and stream protocols, context, HTTP client with a replaying transport, pagination helpers, error taxonomy, fixture recorder and scrubber, golden tests.
- `records.apply_batch` with locking, monotonic clock, hash-gated update, stub resources, state history, links, counts, quarantine.
- Sweep with generation and guard. Raw page archive.
- SANDBOX connector: generator, API-key auth, resources and findings streams, offset pagination, scenario injection.
- A synchronous test harness that runs one stream to completion in-process.

**Exit.** SANDBOX passes conformance properties 1 to 9 through the harness. The concurrency test finds zero skipped changes. Re-syncing an unchanged tenant writes zero rows.

### M3: Sync engine (about 4)
- Schedules, jobs, stream runs, the scheduler loop, admission with priority, fairness and caps.
- Slice handler on Absurd, heartbeats, the three timeouts, cancellation, outcome mapping, retries, parking.
- Checkpoints with optimistic versions. Rate buckets with leasing and header correction.
- Health classification and roll-up. On-demand jobs and reset.
- Token providers: static, client credentials, OAuth2 refresh, with single-flight and the failure policy.

**Exit.** Engine scenario tests pass: kill at every page boundary and resume to the same result, a 20-minute rate-limit reset parks the run and frees the worker, a vendor 500 retries on schedule and a 401 does not, a tenant with 500 queued runs does not delay another tenant's on-demand job past 60 seconds, 50 concurrent readers of an expiring token cause one refresh, two quick on-demand POSTs return the same job.

### M4: Connections, connect flow, first GitHub sync (about 3)
- Vault end to end: seal in the API, open in workers, binding check.
- Connection lifecycle and the transition table. Verify and probe tasks, grants, fingerprint, test endpoint, credential rotation with verification.
- Connect sessions, the hosted connect page, the schema-driven form (proven with SANDBOX), `connect-js`.
- Register the platform GitHub App. The `GitHubApp` token provider. The install flow with OAuth verification and its edge cases.
- GitHub `repositories` and `branches` streams with fixtures and golden output.
- `tools/github-seed`, first version.

**Exit.** Installing the app from the connect UI creates an ACTIVE connection with no copy-paste, and repositories from the seeded organization appear through `GET /v1/resources`. A callback carrying an installation id the user cannot access is rejected and audited. This matches the research plan's sprint 1 exit, "first end-to-end sync of seeded GitHub org".

### M5: GitHub alerts and the data API (about 3)
- The three alert streams: organization and per-repository modes, backfill, incremental walk with watermark, weekly reconcile, feature-not-enabled handling.
- Mapping tables, golden output, generated mapping docs and capabilities.
- Data endpoints: both scopes, every Leen filter, sorting, signed cursors, `updatedSince` with cursor, deletes in the feed, `changeType`, `include=resources`, unsupported-filter header.
- Idempotency keys and API rate limiting.
- Dashboard: Connections, connection detail, Jobs, and the findings and resources explorer.

**Exit.** GitHub passes the full conformance suite. API contract tests cover every filter. An idle hourly cycle on the seeded organization costs fewer than 30 requests. The nightly live sync is running. A GitHub App without the Dependabot permission connects with health `UNAUTHORIZED` naming that stream.

### M6: Events and webhooks (about 3)
- Outbox written in every state-changing transaction. Dispatcher. Per-connection sequence.
- Webhook endpoints, signing with dual secrets on rotation, delivery tasks with the retry schedule, SSRF guard, delivery log, replay, auto-disable. The pull feed.
- Inbound: the ingress endpoint, signature verification, idempotent delivery storage, routing, connector webhook effects, dirty records and targeted refresh, installation lifecycle handling, failed-delivery redelivery.
- Dashboard: Webhooks.

**Exit.** Killing the dispatcher mid-delivery loses no events. A receiver that is down for 3 hours receives every event. Dismissing an alert in GitHub updates our finding within 2 minutes. Uninstalling the app turns the connection `UNAUTHORIZED` and emits exactly one health event. A replayed inbound delivery has no effect.

### M7: Observability, operations and dashboard completion (about 3)
- Operation log and events, job logs endpoint, Logs view.
- Metrics and alerts with runbooks. Vendor outage detection.
- Audit log coverage and its view. Usage metering and the Metrics and Overview pages, including the findings summary endpoint.
- Admin console: cross-account search, scheduler view, raw page viewer, repair tools.
- Retention tasks and the partition manager.
- The request console replaces the playground. The mock store and the Workflows page are deleted.

**Exit.** No view reads the mock store, and it is gone from the repository. Every alert has a runbook. An operator resolves a stuck connection without touching the database. The secret-hygiene test finds no canary values anywhere.

### M8: Platform breadth beyond GitHub (about 3)
Everything a later connector needs that GitHub does not, each proven with SANDBOX.

- Async export primitive with polling, chunked download and resume.
- Vendor retention-aware schedules. Page-token pagination. `since`-filter incremental.
- OAuth2 authorization-code connect flow with PKCE, through the same connect UI.
- Sandbox connections for both connectors.
- Enrichment: NVD mirror task, GHSA and OSV aliasing, KEV and EPSS, read-time join, the CVE lookup endpoint.
- Read-only passthrough with an allowlist per connector.
- Re-normalisation from the raw archive.
- CDK scaffold command, dry-run CLI, coverage report.

**Exit.** A SANDBOX export of 1 million findings completes and resumes correctly after a worker is killed mid-download. A GHSA-only Dependabot alert gains its CVE alias. Scaffolding a new connector and making it pass conformance against a toy API takes one engineer under a day, with zero changes outside `packages/connectors/`. That last test is the plan's central claim, so it is run for real, by someone who did not build the CDK.

### M9: GitHub completeness (about 3)
- Customer-owned apps, GHES and GHE.com: registration walkthrough, base URL validation, version gating, adaptive rate budget.
- Secret locations option, branch scope options, secret severity option.
- Write-back: the action plane, the read-and-write app, `finding.set_state` for all three families, the round-trip re-fetch.
- Resolve every remaining spike in section 6.
- Seed organization completed with every state and edge case in part 6, section 12.

**Exit.** A connection to a GHES or GHE.com instance syncs all supported streams (needs a test instance, see section 7). Dismissing a finding through our API shows as dismissed in GitHub and comes back `IGNORED` on the next read. Every GitHub fact marked "verify" in part 6 is confirmed or its fallback is in place.

### M10: Hardening and launch readiness (about 3)
- Load test at the year-one target. The benchmark gates in section 8.
- Vendor payload encryption turned on. Vault key rotation drill. Backup restore drill.
- Rolling-deploy test under load.
- Docs site: reference, guides, per-connector pages, webhook verification samples in four languages, Leen migration guide.
- Published TypeScript and Python clients generated from the OpenAPI document.
- Dogfood: the SecureFabric repository connected through the platform's own GitHub connector.

**Exit.** All benchmark gates pass. A Leen V2 client passes our contract tests after the changes the migration guide lists. Zero 5xx during a rolling deploy under load.

**Total: about 32 engineer-weeks.**

## 3. Work lanes

With four engineers the milestones are not strictly sequential. Four lanes run from M1 onward:

| Lane | Owns | Critical in |
|---|---|---|
| A. Core | Schema, write path, scheduler, engine | M2, M3 |
| B. Connectors | CDK, SANDBOX, GitHub, seed organization | M2, M4, M5, M9 |
| C. API and events | Endpoints, auth, vault, outbox, webhooks | M1, M5, M6 |
| D. Dashboard | Views, connect UI, admin console, docs | M1, M4, M7 |

The critical path is A: M2 then M3. Lanes B, C and D can stay ahead of it because SANDBOX and the in-process harness let connectors and the data API be built before the scheduler exists. With that parallelism, 32 engineer-weeks is roughly 10 to 12 calendar weeks for four people.

## 4. What this means for the February plan

The research plan (`vuln-appsec-reference.md`) schedules ten connectors by 26 February 2027 alongside the platform, with Tenable in sprint 2. This plan spends that capacity differently: the whole platform and one connector done completely, then connectors added quickly.

That is a real trade and should be decided deliberately:

- The research estimate for the wave-0 platform was 9.5 to 13.5 engineer-weeks. This plan's platform work is about 26 (32 less roughly 6 of GitHub-specific work), because it includes most P1 requirements, the SANDBOX connector, write-back, the admin console and hardening that the research plan left implicit or later.
- At 10 to 12 calendar weeks, the platform and GitHub land around mid-February, leaving little of the 13-week window for the other nine connectors.
- The mitigation is in M8's exit test. If a connector really is a manifest, a module and fixtures, the simpler tier-A connectors (Socket, SonarQube, Semgrep, at 1 to 2 engineer-weeks each in the research estimate) can start in lane B from M5 onward, overlapping M6 to M10, without waiting for launch hardening.

If the February date is fixed and ten connectors are required, the alternative is to stop the platform at M6, start connectors there, and push M7's admin console, M8's enrichment and passthrough, and M9's GHES and write-back past February. The plan supports that cut cleanly because those milestones do not change earlier ones.

## 5. Requirement traceability

Every requirement family, where it is designed, and when it is built. "Not in this plan" lists each exception by id, so nothing is silently dropped.

| Family | Designed in | Built in | Not in this plan |
|---|---|---|---|
| TEN Tenancy, keys, access | Part 3 | M0, M1 (TEN-12 in M5, TEN-13 in M8) | TEN-10 SSO and SCIM. TEN-11 enforced 2FA. TEN-09 enforced only as admin versus member. All three are WorkOS configuration later. |
| CAT Catalogue | Part 5 | M1, M5 (CAT-03 generated capabilities) | CAT-07 public changelog process. CAT-06's 90-day deprecation process (the version and deprecated fields exist). |
| AUTH Credentials | Parts 3, 6 | M3, M4, M8 | AUTH-13 relay agent. AUTH-14 mutual TLS. AUTH-01's AWS role mode is an interface only. AUTH-02's Microsoft admin consent is not built, though the generic redirect flow it would use is. |
| CON Connections | Part 3 | M4 (CON-14 in M7) | CON-15 destination connections (column reserved). |
| SYNC Sync engine | Part 4 | M3 (SYNC-16, SYNC-18 in M8, SYNC-19 in M6) | None. SYNC-19 is P2 in the requirements and is built here, because webhooks are central to a complete GitHub connector. |
| RATE Vendor hygiene | Part 4 | M2, M3 (RATE-08 in M7) | Published static egress IPs in RATE-07 are a deployment matter. The egress policy itself is built. |
| NORM Normalisation | Parts 2, 5, 6 | M2, M5 | NORM-12 objects are reserved names only. |
| STORE Record store | Parts 2, 4 | M2 (STORE-11 in M8, STORE-09 in M10, STORE-12 in M7) | STORE-15 customer bucket export. STORE-08's second store is a hook only. |
| API Data API | Part 7 | M5 (API-16 in M7) | API-15 bulk export. API-10 is region-bound keys in one cell. |
| CDC Change consumption | Parts 4, 7 | M5, M6 | CDC-05 record-level events. CDC-06 streaming destinations. |
| HOOK Outbound webhooks | Part 7 | M6 | HOOK-09 per-connection override. |
| ENR Enrichment | Part 7 | M8 | None. |
| DEDUP Correlation | Part 2 | M2 (DEDUP-01 columns) | DEDUP-02, 03, 04. |
| RAW Passthrough | Parts 7, 8 | M8 (RAW-01), M7 (RAW-02) | None. |
| ACT Write-back | Parts 6, 7 | M9 (ACT-02, ACT-03) | ACT-01 tickets, which needs a ticketing connector. |
| OBS Customer observability | Parts 8, 9 | M5, M7 | OBS-04 OTLP export to customers. OBS-05 customer alerts. OBS-06 public status page. |
| OPS Internal operations | Parts 8, 9 | M7 | OPS-04 feature flags. Enabling a connector per environment is covered by integrations, and finer flags are not. |
| DX Developer experience | Part 8 | M7, M10 | DX-06 MCP server. |
| CDK | Part 5 | M2, M5, M8 | None. |
| BILL Usage | Part 2 | M7 (BILL-01, read-only BILL-03) | BILL-02 quota enforcement. |
| SEC Security | Parts 1, 3, 9 | M0 onward | SEC-03's customer-managed keys (rotation is built). SEC-10's penetration test. SEC-04 is met by the vault design, not by tokens (PD-4). |
| COMP Compliance | Part 9 | | SOC 2, GDPR paperwork and the residency audit are process. The architecture supports COMP-03. |
| NFR | Parts 4, 9 | M3, M10 | NFR-10 infrastructure as code for more regions. NFR-11 cost reporting. NFR-01 external availability probes. |

Three requirements are met differently from how they are written, each with its reasoning in part 1: the custom `task` queue (D3) becomes Absurd plus admission, `records_seen` becomes `seen_gen`, and task-scoped worker tokens become the sealed vault.

## 6. Spikes

Facts the research pass could not confirm from documentation. Each is a short experiment against the seeded organization, and each has a fallback already designed, so none can stall a milestone.

| # | Question | Needed by | Fallback if the answer is bad |
|---|---|---|---|
| S1 | Does the setup URL callback echo `state` and include `code` when user authorization during installation is enabled? | M4 | The "already installed" path (plain OAuth, then pick an installation) becomes the only path |
| S2 | Do the organization-level alert listings work with an installation limited to selected repositories, returning only those? | M5 | Per-repository mode for such installations |
| S3 | Does `updated_at` move on every change for each family (auto-dismissal, validity change, new location, reopen)? | M5 | Daily reconcile for the affected stream, and rely on webhooks for latency |
| S4 | Does a stored pagination cursor stay valid across minutes or hours? | M5 | Restart the pass from the beginning. Already the designed behaviour on rejection. |
| S5 | Which permission is the minimum that returns `security_and_analysis` on repositories? | M4 | Coverage is derived from probe results per repository instead |
| S6 | Does `GET /installation/repositories` behave as described, including for user accounts? | M4 | `GET /orgs/{org}/repos` and `GET /user/repos` |
| S7 | Do 304 responses to conditional requests count against the primary rate limit? | M9 | Skip the optimisation. Nothing depends on it. |
| S8 | Minimum GHES version for each organization-level alert endpoint | M9 | Per-repository endpoints on older versions |
| S9 | Does the Dependabot alert payload carry a reachability verdict on the tiers we can test? | M5 | `reachability` stays null and capabilities say unsupported |
| S10 | Exact webhook delivery headers and the redelivery API's behaviour | M6 | Scheduled sync covers missed deliveries regardless |
| S11 | What does Leen return for a GitHub secret finding's severity? | M5 | Our `UNKNOWN` default stands. Matters only for migration fidelity. |
| S12 | Absurd behaviour under our pattern: thousands of short tasks per minute, cleanup cost, claim latency | M3 | Tune queue partitioning and cleanup. Absurd already supports partitioned queues. |

S1 to S6 should be run in the first week, in parallel with M0, because they need only a registered test app and the seeded organization.

## 7. Decisions that need you

The plan makes a default choice for each so work is not blocked, but these are yours.

1. **Platform versus February connector count.** Section 4. Default: follow this plan and start simple connectors from M5.
2. **Replacing the mock schema and domain package.** They were being edited while this plan was written. Default: replace (PD-7). If that work is meant to be kept, say so before M0.
3. **Shared GitHub App as the default.** It makes onboarding one click and means all tenants on github.com depend on one app registration and its standing with GitHub. Default: shared, with customer-owned supported.
4. **Secret finding severity.** `UNKNOWN` by default is honest and makes secrets invisible to severity filters. The alternative is deriving it from validity by default and flagging it as derived. Default: `UNKNOWN`, with the opt-in.
5. **Dropping the Contents permission.** The research card includes it. Default: do not request it.
6. **Write-back in scope.** The requirements rate it P2 and after February. It is included in M9 because it completes GitHub and builds the action plane once. Default: include. It is the cheapest milestone to cut.
7. **Access to a GHES or GHE.com instance** for M9. Without one, that part is designed and built, but verified only against github.com.
8. **Region and hosting.** The plan builds one cell and is silent on cloud provider, KMS and managed Postgres. Needed before M10, and the `KeyProvider` and blob interfaces keep the choice open until then.

## 8. Benchmark gates

Run in M10 against synthetic data at the year-one target. A failed gate has a named fix.

| Gate | Target | If it fails |
|---|---|---|
| List findings, limit 100, connection scope | p95 at most 500 ms at 50 requests a second (NFR-04) | Covering indexes for the common filter and sort pairs |
| Get by id | p95 at most 150 ms | |
| Organization-scoped list across 20 connections | p95 at most 1 s | Per-organization index tuning, or cap fan-out |
| `lastSeenSince` on a 1-million-finding connection | p95 at most 2 s | Add the index and coarsen `last_seen_at` to the hour |
| Ingest | At least 2,000 records a second per worker (NFR-05) | `COPY` into a staging table, then merge |
| 1-million-finding backfill | Under 2 hours where the vendor allows | Parallel chunk writers under the export primitive |
| Weekly reconcile of 100 million rows | Autovacuum keeps dead tuples under 20% per partition | Partition-level autovacuum settings, lower fillfactor |
| Admission | 200 admitted runs a second, lag under 5 s | Batch admission, or shard the scheduler by environment hash |
| Outbox | 99% of events delivered within 60 s (NFR-03) | More delivery workers. The dispatcher is not the bottleneck by design. |
| Scale-out | Doubling sync workers roughly doubles throughput (NFR-07) | Find the shared lock |

## 9. Definition of done

The platform is done, in the sense the goal asks for, when all of these hold:

1. GitHub passes the conformance suite, the nightly live sync has been green for two weeks, and every item in part 6 is built or explicitly listed as optional.
2. SANDBOX passes the conformance suite, including the primitives GitHub does not use.
3. The M8 exit test has been run: a new connector built by someone who did not write the CDK, with no change outside `packages/connectors/`.
4. Every requirement is either built or named in section 5's last column.
5. The dashboard has no mock data.
6. All benchmark gates pass.
7. Every spike in section 6 is closed.
