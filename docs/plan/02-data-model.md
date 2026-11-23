# Part 2: Data model

One Postgres 17 database, six schemas. `absurd` is the vendored queue. The other five are ours.

| Schema | Holds | Tenant rows |
|---|---|---|
| `control` | Accounts, users, environments, API keys, organizations, connectors, vendor apps, integrations, connections, credentials, connect sessions | Yes |
| `sync` | Schedules, jobs, stream runs, checkpoints, rate buckets, inbound webhook deliveries, dirty records, raw page index | Yes |
| `data` | Resources, findings, links, state history, quarantine, stream heads, plus the global CVE mirror | Yes (except `cve`) |
| `events` | Outbox, webhook endpoints, deliveries, attempts | Yes |
| `obs` | Operation log, audit events, usage events | Yes |

## 1. Conventions

- **Primary keys.** Control-plane rows use UUIDv7 (`absurd.portable_uuidv7()` already exists in the database, and Postgres 18's native `uuidv7()` replaces it later). Canonical records use UUIDv5 so the same vendor record always gets the same id (STORE-01). Public ids are plain UUIDs, as in Leen.
- **Tenant key.** Every tenant row carries `environment_id uuid not null`. It is denormalised onto child tables on purpose, so row-level security needs no joins.
- **Row-level security.** Enabled on every tenant table with one policy: `environment_id = current_setting('app.environment_id')::uuid`. The application sets it with `set local` inside `tenant_tx(environment_id)`, a helper in `packages/db`. Background roles that legitimately work across tenants (scheduler, retention) connect as a role with `bypassrls` and are the only code paths allowed to. A CI test opens a transaction with no setting and asserts every tenant table returns zero rows.
- **Soft delete.** `deleted_at timestamptz`. Uniqueness among live rows uses partial unique indexes `where deleted_at is null`. (Nango used composite uniques including `deleted_at`, then had to patch them with `NULLS NOT DISTINCT`, and one table was missed. Partial indexes avoid the trap.)
- **Enumerations.** `text` with `check` constraints, not Postgres enum types, so adding a value is an ordinary migration.
- **Timestamps.** `timestamptz`, UTC. API output is ISO 8601 with milliseconds (NORM-13).
- **Migrations.** Forward-only SQL files, expand then contract (NFR-09): add nullable, backfill, switch reads, then drop.
- **Foreign keys.** Within the control plane, real foreign keys. From partitioned data tables to control tables, none: `connection_id` is a soft reference, because purge is done by dropping or bulk-deleting per connection and history must be able to outlive a connection.

## 2. `control` schema

### account
The customer company. Maps one to one to a WorkOS organization.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `name`, `slug` | text | `slug` unique |
| `workos_organization_id` | text unique | |
| `plan` | text | Used for limits later (BILL-02) |
| `created_at` | timestamptz | |

### app_user, membership
`app_user(id, workos_user_id unique, email, name, created_at, last_seen_at)`.
`membership(account_id, user_id, role, created_at)`, PK `(account_id, user_id)`, `role in ('admin','developer','support')`. Roles follow TEN-09. Enforcement in the first release is coarse (admin versus everyone else), but the column carries all three from day one.

### environment

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `account_id` | uuid FK | |
| `slug`, `name` | text | unique `(account_id, slug)` where live. The dashboard's `[env]` route segment is the slug. |
| `is_production` | bool | Drives key prefix and RBAC |
| `settings` | jsonb | Connect UI branding, allowed redirect origins, default sync interval |
| `vault_public_key` | bytea | X25519 public key. Readable by the API. |
| `vault_private_key_wrapped` | bytea | Private key wrapped by the KEK. Opened only by workers. |
| `vault_key_version` | int | For rotation (SEC-03) |
| `created_at`, `deleted_at` | timestamptz | |

### api_key

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `environment_id` | uuid FK | |
| `name` | text | |
| `prefix` | text | First 12 characters, shown in the UI, e.g. `sfk_live_us_a1b2` |
| `hash` | bytea unique | HMAC-SHA256 of the full key under a server-side pepper. Keys are 256-bit random, so a fast keyed hash is right. A slow password hash would only add latency to every request. |
| `scopes` | text[] | `provisioning:read`, `provisioning:write`, `data:read`, `jobs:execute`, `webhooks:manage`, `keys:manage`, `actions:write` |
| `created_by` | uuid | |
| `last_used_at` | timestamptz | Updated at most once a minute per key |
| `expires_at`, `revoked_at` | timestamptz | |

Several live keys per environment are allowed (TEN-08). There is no "default key" stored in plaintext, unlike the mock.

### organization
The customer's end customer.

`id`, `environment_id`, `identifier` (customer-chosen), `name`, `metadata jsonb`, `created_at`, `updated_at`, `deleted_at`. Unique `(environment_id, identifier) where deleted_at is null`. Trigram index on `name` and `identifier` for search (TEN-04).

### connector
The catalogue, loaded from manifests at deploy.

`id text` (e.g. `GITHUB`), `version text` (semver), `manifest jsonb`, `status in ('beta','ga','deprecated')`, `is_current bool`, `deprecated_at`, `loaded_at`. PK `(id, version)`. Partial unique `(id) where is_current`. Not tenant data, readable by all.

### vendor_app
A registration with a vendor that connections authenticate through. For GitHub this is a GitHub App.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | Appears in the inbound webhook URL |
| `environment_id` | uuid null | Null means platform-owned and shared by every tenant |
| `connector_id` | text | |
| `name` | text | |
| `base_url` | text | `https://github.com`, `https://acme.ghe.com`, or a GHES host. Validated by the egress policy. |
| `config` | jsonb | Non-secret: `app_id`, `slug`, `client_id`, API base URL, permission tier (`read` or `read_write`) |
| `secrets_sealed` | bytea | App private key and OAuth client secret. Sealed to the environment key, or to a platform key pair for platform-owned apps. |
| `ingress_secret_enc` | bytea | Webhook secret, encrypted under the ingress key the API holds |
| `created_at`, `deleted_at` | timestamptz | |

RLS policy here is `environment_id is null or environment_id = current setting`, and writes to platform-owned rows are restricted to an operator role.

### integration
One environment's use of a connector.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `environment_id` | uuid FK | |
| `connector_id` | text | |
| `key` | text | Slug, unique per environment where live. The default one is the lowercased connector id. |
| `display_name` | text | |
| `vendor_app_id` | uuid null | Null means the platform's default app for this connector |
| `enabled_streams` | text[] | Subset of the manifest's streams |
| `stream_intervals` | jsonb | Default interval per stream, in seconds |
| `option_defaults` | jsonb | Validated against the manifest's option schema |
| `write_back_enabled` | bool | Part 6, section 10 |
| `created_at`, `deleted_at` | timestamptz | |

### connection

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `environment_id`, `organization_id`, `integration_id` | uuid | |
| `connector_id`, `connector_version` | text | Version pinned to a major |
| `identifier` | text null | Customer key, unique per organization where live |
| `state` | text | `PENDING`, `ACTIVE`, `PAUSED`, `DELETED`, `HARD_DELETED` (CON-02) |
| `direction` | text default `'SOURCE'` | Reserved for destination connections (CON-15). Only `SOURCE` is implemented. |
| `is_sandbox` | bool | Replays fixtures, never calls the vendor |
| `options` | jsonb | Validated against the manifest |
| `connection_config` | jsonb | Non-secret vendor parameters. For GitHub: `installation_id`, `account_login`, `account_id`, `account_type`, `repository_selection`. |
| `vendor_tenant_ref` | text | The value inbound webhooks route by. For GitHub, the installation id. Indexed with `integration.vendor_app_id`. |
| `tenant_fingerprint` | bytea | Hash of vendor tenant identity, for duplicate detection (AUTH-10) |
| `metadata` | jsonb | Customer JSON, at most 16 KB (CON-10) |
| `tags` | jsonb | At most 10 pairs, GIN indexed (TEN-05) |
| `health_status` | text | `INITIALIZING`, `HEALTHY`, `UNHEALTHY` |
| `health_code` | text | See part 3, section 7 |
| `resolution_owner` | text | `PLATFORM`, `CUSTOMER`, `VENDOR` |
| `health_details` | jsonb | |
| `health_changed_at` | timestamptz | |
| `event_seq` | bigint | Per-connection outbox sequence (HOOK-11), incremented under row lock |
| `data_shard` | text default `'primary'` | Reserved routing hook (STORE-08) |
| `created_at`, `updated_at`, `deleted_at`, `purge_after` | timestamptz | |

Indexes: `(environment_id, organization_id)`, `(environment_id, health_code)`, `(vendor_tenant_ref)`, partial unique `(organization_id, identifier) where deleted_at is null`, partial unique `(organization_id, integration_id, tenant_fingerprint) where deleted_at is null`.

### credential
One row per connection. Deleted, not soft-deleted, the moment a connection is deleted (CON-04).

| Column | Type | Notes |
|---|---|---|
| `connection_id` | uuid PK, FK cascade | |
| `environment_id` | uuid | |
| `auth_mode` | text | `APP`, `API_KEY`, `BASIC`, `OAUTH2`, `OAUTH2_CC`, `AWS_ROLE` |
| `sealed` | bytea | Long-lived secret material, sealed to the environment key. Empty for GitHub, where the secret is the app's key on `vendor_app`. |
| `token_sealed` | bytea | Cached short-lived access token |
| `token_expires_at` | timestamptz | |
| `vault_key_version` | int | |
| `last_refresh_at`, `last_refresh_failure_at` | timestamptz | |
| `refresh_fail_days` | int | Counted at most once per calendar day (AUTH-06) |
| `refresh_exhausted` | bool | After 4 consecutive failing days |
| `updated_at` | timestamptz | |

### connection_grant
The per-stream result of the permission probe (AUTH-08). One row per `(connection_id, stream)`.

`status in ('GRANTED','UNAUTHORIZED','NOT_ENABLED','UNSUPPORTED','UNKNOWN')`, `endpoint text`, `detail text`, `checked_at`.

`NOT_ENABLED` is distinct from `UNAUTHORIZED` and matters for GitHub: a repository without secret scanning is not a failure, it is a coverage fact.

### connect_session
The invite token of CON-06.

`id`, `environment_id`, `organization_id`, `token_hash bytea unique`, `allowed_integration_ids uuid[]`, `connection_id uuid null` (set for re-authorisation), `option_presets jsonb`, `redirect_success`, `redirect_error`, `expires_at` (default 30 minutes), `used_at`, `created_at`.

### oauth_state
`state text PK` (random, 256 bits), `connect_session_id`, `vendor_app_id`, `code_verifier` (PKCE where the vendor supports it), `expires_at` (10 minutes), `consumed_at`. Rows are purged after 2 days.

### connection_health_event
Health history (CON-14). `connection_id`, `environment_id`, `from_code`, `to_code`, `job_id`, `at`. Range-partitioned by month, 30 days served by the API, 13 months kept.

### idempotency_key
`(environment_id, key)` PK, `request_hash`, `status`, `response jsonb`, `created_at`. Rows live 24 hours (API-08).

## 3. `sync` schema

### stream_schedule
One per `(connection, stream)`.

`id`, `environment_id`, `connection_id`, `stream`, `interval_s`, `state in ('STARTED','PAUSED','DELETED')`, `next_run_at`, `full_every_s` (how often an incremental stream does a full reconcile pass), `next_full_at`, `last_success_at`, `last_run_id`. Unique `(connection_id, stream)`. Index `(next_run_at) where state = 'STARTED'`.

`last_success_at` is the freshness source (SYNC-17).

### job
The customer-visible run record (SYNC-07). A job groups the stream runs started together for one connection.

`id`, `environment_id`, `connection_id`, `type in ('INITIAL','SCHEDULED','ON_DEMAND','WEBHOOK','RETRY')`, `status in ('QUEUED','RUNNING','SUCCESS','PARTIAL','FAILED','CANCELLED')`, `requested_by`, `options jsonb` (e.g. `force_full_refresh`, `since`), `health_code`, `failure_reason`, `created_at`, `started_at`, `finished_at`. Index `(connection_id, created_at desc)`. Kept 90 days.

Job status is derived from its runs: all succeeded is `SUCCESS`, a mix is `PARTIAL` (SYNC-15), none is `FAILED`.

### stream_run
The unit the scheduler admits and a worker executes. This table is the real queue.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `job_id`, `environment_id`, `connection_id` | uuid | |
| `stream` | text | |
| `mode` | text | `backfill`, `incremental`, `full`, `targeted` |
| `state` | text | `QUEUED`, `ADMITTED`, `RUNNING`, `PARKED`, `RETRY_WAIT`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `EXPIRED` |
| `priority` | smallint | 0 webhook-targeted and on-demand, 1 initial, 2 scheduled |
| `fair_key` | text | `environment_id/organization_id` |
| `budget_key` | text | Rate-budget identity, e.g. `GITHUB:<vendor_app_id>:<installation_id>` |
| `attempt` | int | |
| `not_before` | timestamptz | Earliest admission time. Used for backoff and for parking until a rate-limit reset. |
| `deadline_at` | timestamptz | Run timeout (SYNC-09) |
| `absurd_task_id` | uuid null | The current execution slice |
| `cancel_requested` | bool | |
| `generation` | bigint | For sweeps. Taken from a sequence when a full pass starts and kept across retries. |
| `added`, `updated`, `deleted`, `unchanged`, `quarantined` | int | |
| `pages`, `vendor_requests` | int | |
| `health_code` | text | Outcome classification |
| `error` | jsonb | Redacted |
| `created_at`, `admitted_at`, `started_at`, `finished_at` | timestamptz | |

Indexes:
- Partial unique `(connection_id, stream) where state in ('QUEUED','ADMITTED','RUNNING','PARKED','RETRY_WAIT') and mode <> 'targeted'`. This is SYNC-08: at most one active run per stream, enforced by the database. It also bounds queue growth by construction, where Nango needs a per-group task cap that drops work.
- `(priority, not_before, created_at) where state in ('QUEUED','PARKED','RETRY_WAIT')` for admission.
- `(budget_key) where state in ('ADMITTED','RUNNING')` and `(environment_id) where state in ('ADMITTED','RUNNING')` for concurrency counts.

### checkpoint
`(connection_id, stream, key)` PK, `environment_id`, `value jsonb`, `version int`, `updated_at`. `key` is `default`, `sweep` or `export`. Writes are `update ... where version = $expected`, and a mismatch aborts the batch (SYNC-04).

### concurrency_limit
Overrides for the defaults. `(scope_kind, scope_id)` PK where `scope_kind in ('global','environment','connector','budget')`, `max_running int`.

### rate_bucket
Shared vendor rate budgets (RATE-03). `key text PK`, `capacity`, `tokens`, `refill_per_s`, `reset_at`, `vendor_remaining`, `vendor_limit`, `updated_at`. Part 4, section 6.

### ingress_delivery
Inbound vendor webhooks. `id`, `vendor_app_id`, `delivery_id` (GitHub's `X-GitHub-Delivery`), `event`, `action`, `vendor_tenant_ref`, `payload jsonb`, `status in ('RECEIVED','ROUTED','IGNORED','FAILED')`, `received_at`, `processed_at`. Unique `(vendor_app_id, delivery_id)`, which makes redelivery idempotent. Daily range partitions, dropped after 7 days. No `environment_id`, because a shared app's delivery can fan out to several tenants. The API never returns these rows to customers.

### dirty_record
The queue of single records to re-fetch. `(connection_id, stream, vendor_key)` PK, `environment_id`, `reason`, `enqueued_at`. The primary key collapses bursts of webhooks for the same alert into one fetch.

### raw_page
Index of the raw page archive (STORE-10). `id`, `environment_id`, `connection_id`, `stream_run_id`, `seq`, `blob_key`, `bytes`, `request_summary jsonb` (method, path, status, no headers), `created_at`, `expires_at`. Daily partitions. The bytes live in object storage, encrypted, with a 7-day lifecycle rule.

## 4. `data` schema: canonical objects

Two objects, Leen V2 compatible (NORM-01). Both tables are hash-partitioned by `connection_id` into 64 partitions. A connection's rows always sit in one partition, so every connection-scoped query touches one partition, and purging a connection is a single-partition delete.

Sixty-four is a deliberate middle: Nango uses 256 partitions on `(connection_id, model)` for a generic record store. Our tables are typed, wider, and carry more indexes, and each index exists once per partition. Sixty-four keeps partitions well under a few million rows at the year-one target of 100 million findings while keeping planning time and index count modest.

### resource

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | UUIDv5(namespace, `connection_id \| 'resource' \| natural_key`) |
| `environment_id`, `organization_id`, `connection_id` | uuid | |
| `stream` | text | The stream that owns this row. Scopes sweeps. |
| `natural_key` | text | At most 512 characters, documented per connector |
| `type` | text | `BRANCH`, `HOST`, `CONTAINER`, `DEPENDENCY`, `IMAGE`, `REPOSITORY`, `VENDOR`, `KUBERNETES`, `FUNCTION`, `SOFTWARE`, `UNKNOWN` |
| `state` | text | `ACTIVE`, `IGNORED`, `DELETED`, `INACTIVE`, `QUARANTINED`, `UNKNOWN` |
| `name`, `url` | text | |
| `groups`, `tags` | jsonb | |
| `data` | jsonb | Type-specific block (`repository`, `branch`, `host`, ...) |
| `cloud_metadata` | jsonb | |
| `vendor_id` | text | |
| `vendor_data` | bytea | Compressed vendor payload with a format header (PD-12) |
| `is_stub` | bool | Created as a placeholder by a finding that arrived before its resource (NORM-14) |
| `entity_id` | uuid null | Reserved for correlation (DEDUP-01) |
| `hash` | bytea | SHA-256 over canonical JSON of material fields |
| `seen_gen` | bigint | Generation of the last pass that observed the row |
| `first_seen_at`, `last_seen_at` | timestamptz | `last_seen_at` is observational and does not move `updated_at` |
| `created_at`, `updated_at`, `deleted_at` | timestamptz | |

Keys and indexes: PK `(connection_id, id)`, unique `(connection_id, natural_key)`, `(connection_id, updated_at, id)`, `(connection_id, type, state)`, `(id)`, `(organization_id, updated_at, id)`.

### vulnerability_finding

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | UUIDv5(namespace, `connection_id \| 'finding' \| natural_key`) |
| `environment_id`, `organization_id`, `connection_id` | uuid | |
| `stream`, `natural_key` | text | |
| `type` | text | `DEPENDENCY`, `CODE`, `SECRET`, `CONTAINER`, `IAC`, `HOST`, `DOMAIN`, `UNKNOWN` |
| `title`, `description` | text | |
| `severity` | text | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`, `UNKNOWN` |
| `severity_rank` | smallint | 5 to 0, so sorting by severity is an index order, not a `case` expression |
| `state` | text | `OPEN`, `CLOSED`, `REOPENED`, `IGNORED`, `DELETED`, `UNKNOWN` |
| `state_updated_at` | timestamptz | |
| `has_fix`, `exploitable` | bool null | Tri-state. Null means the vendor made no assertion (NORM-06). |
| `reachability` | text null | `REACHABLE`, `POTENTIALLY_REACHABLE`, `UNREACHABLE`, `UNKNOWN`, or null |
| `remediation`, `analytic`, `analytic_output`, `product`, `ticket` | jsonb | Leen shapes |
| `resource_related` | jsonb | `affected_code`, `affected_package`, `affected_image`, `port`, ... |
| `vulnerabilities` | jsonb | Vendor-supplied CVE entries with CVSS scores and weaknesses |
| `cve_ids` | text[] | Denormalised, uppercase, GIN indexed |
| `enrichment` | jsonb | NVD, KEV, EPSS. Filled at read time from `data.cve` in the first release, see part 7, section 6. |
| `meta_derived` | text[] | Names of fields the platform derived, surfaced as `_meta.derived` (NORM-09) |
| `vendor_id`, `vendor_url`, `vendor_severity`, `vendor_state` | text | The `vendor_attributes` scalars |
| `vendor_created_at`, `vendor_updated_at` | timestamptz | |
| `vendor_identifiers` | jsonb | `vulnerability_identifiers` |
| `vendor_data` | bytea | |
| `cluster_id` | uuid null | Reserved for correlation |
| `hash` | bytea | |
| `seen_gen` | bigint | |
| `first_seen_at`, `last_seen_at` | timestamptz | |
| `created_at`, `updated_at`, `deleted_at` | timestamptz | |

Keys and indexes: PK `(connection_id, id)`, unique `(connection_id, natural_key)`, `(connection_id, updated_at, id)`, `(connection_id, state, severity_rank desc, id)`, `(connection_id, state_updated_at, id)`, `(connection_id, first_seen_at, id)`, `(id)`, `(organization_id, updated_at, id)`, GIN `(cve_ids)`.

Two deliberate omissions:

- **No index on `last_seen_at` or `seen_gen`.** Both change on every observation. Leaving them unindexed keeps those writes heap-only (HOT) updates that touch no index. `lastSeenSince` and sorting by `last_seen` therefore scan one connection's partition slice. Part 10 has a benchmark gate for this. If it fails, the fix is an index plus coarsening `last_seen_at` to the hour so most observations do not change the value.
- **`vendor_data` stays on the row.** Postgres stores large values out of line and does not rewrite them when an update leaves the column unchanged, so this gets the benefit of Nango's separate `records_data` table without a second table and join.

### finding_resource
`(connection_id, finding_id, resource_id)` PK, `environment_id`, `role in ('primary','related')`. Same hash partitioning. Index `(connection_id, resource_id)` for the `resourceId` filter.

### state_history
Append-only (STORE-07). `environment_id`, `connection_id`, `record_id`, `object_type`, `from_state`, `to_state`, `at`, `source in ('vendor','platform','sweep')`, `stream_run_id`. Range-partitioned by month, 13 months kept. Index `(connection_id, record_id, at)`.

### quarantine
Records that failed canonical validation (NORM-08). `id`, `environment_id`, `connection_id`, `stream`, `stream_run_id`, `natural_key`, `errors jsonb`, `raw_page_id`, `created_at`. Kept 30 days.

### stream_head
One row per `(connection_id, stream)`. Serves two purposes: record counts (STORE-14) and the monotonic clock for `updated_at` (PD-6).

`environment_id`, `object_type`, `live_count bigint`, `deleted_count bigint`, `bytes bigint`, `head_updated_at timestamptz`, `last_generation bigint`.

It is updated in the same transaction as each batch, under the same advisory lock, so counts are exact by construction and no trigger is needed.

### cve and advisory_alias (global, not tenant data)
`cve(cve_id PK, description, cvss jsonb, cwe text[], references jsonb, published_at, modified_at, kev jsonb, epss jsonb, source_modified_at)`.
`advisory_alias(alias PK, cve_id, source)` maps GHSA and OSV ids to CVE ids (ENR-06).

## 5. `events` and `obs` schemas

### events.outbox_event
`id` (UUIDv7, also the public event id), `environment_id`, `organization_id`, `connection_id`, `sequence bigint` (from `connection.event_seq`), `type`, `payload jsonb` (the full envelope), `created_at`, `dispatched_at`. Index `(id) where dispatched_at is null` for the dispatcher, and `(environment_id, id)` for the pull feed. Monthly range partitions, 90 days kept.

### events.webhook_endpoint
`id`, `environment_id`, `url`, `description`, `event_types text[]`, `secret_sealed bytea`, `previous_secret_sealed bytea`, `previous_secret_expires_at`, `enabled`, `disabled_reason`, `failing_since`, `created_at`, `deleted_at`. At most 5 live rows per environment, enforced in the service and by a trigger.

### events.webhook_delivery
One row per (event, endpoint). `id`, `environment_id`, `event_id`, `endpoint_id`, `status in ('PENDING','DELIVERED','FAILED','DEAD')`, `attempts int`, `next_attempt_at`, `last_status_code`, `last_latency_ms`, `last_error`, `created_at`, `delivered_at`. Unique `(event_id, endpoint_id)`.

### events.webhook_attempt
`delivery_id`, `attempt`, `at`, `status_code`, `latency_ms`, `response_excerpt` (first 1 KB), `error`. Kept 30 days.

### obs.operation
The customer-visible log (OBS-01). One row per logical operation: a stream run, a verification, a connect attempt, an action, an inbound webhook, a webhook delivery.

`id`, `environment_id`, `connection_id`, `organization_id`, `kind in ('sync','auth','action','webhook_in','webhook_out','passthrough')`, `action`, `status in ('running','success','failed','warning','cancelled')`, `job_id`, `stream_run_id`, `request_id`, `started_at`, `duration_ms`, `summary jsonb` (counts, health code). Daily range partitions, 30 days kept (OBS-03). Index `(environment_id, started_at desc)`, `(connection_id, started_at desc)`.

This keeps the shape the dashboard's Logs view already has (`type`, `action`, `status`, `duration`), so that view survives the move to real data.

### obs.operation_event
Lines within an operation: one per vendor HTTP call or log message. `operation_id`, `environment_id`, `at`, `level`, `kind in ('http','log')`, `message`, `http jsonb` (method, path template, status, duration, retry number, rate-limit remaining). Bodies and headers are never stored. Daily partitions, 30 days.

### obs.audit_event
Who did what (SEC-08). `id`, `environment_id`, `account_id`, `actor_kind in ('user','api_key','support','system')`, `actor_id`, `action`, `target_kind`, `target_id`, `ip`, `user_agent`, `request_id`, `detail jsonb`, `at`. Monthly partitions, 1 year kept. Append-only: the application role has insert and select only.

### obs.usage_event and obs.usage_daily
Raw metering events (connection became active, API call batch, job finished) and a daily rollup per environment: active connections, records stored, API calls, jobs (BILL-01).

## 6. Identity and hashing rules

**Record id.** `uuid5(NAMESPACE, f"{connection_id}|{object_kind}|{natural_key}")`. The namespace is a fixed UUID committed to the repo and never changed. The natural key is the connector's choice and must be built from identifiers the vendor never reuses or renames. For GitHub that means the numeric repository id, never the repository name (part 6, section 5).

**Material hash.** SHA-256 over a canonical JSON encoding of the record's material fields: keys sorted, no insignificant whitespace, timestamps normalised to UTC milliseconds, floats formatted by a fixed rule. Excluded from the hash: `last_seen_at`, `seen_gen`, vendor scan identifiers, and the raw `vendor_data`. A record whose hash is unchanged is not rewritten apart from the observational columns, and its `updated_at` does not move (STORE-02, STORE-03, D5).

Nango hashes `JSON.stringify` output, which depends on key order. The canonical encoder exists to avoid that class of false change, and it has property tests.

## 7. Reserved for later, already in the schema

- `resource.entity_id` and `vulnerability_finding.cluster_id` for cross-source correlation.
- `connection.data_shard` for moving a tenant to another database.
- The `FUNCTION` and `SOFTWARE` resource types.
- Object namespaces for Detection, Compliance, Identity and Device (NORM-12): the `data` schema, the `schema` package and the URL space reserve the names. No tables are created until a connector needs them.
- `credential.auth_mode` values that GitHub does not use.

## 8. Requirement tables this model changes

The requirements document sketches 24 tables. This model keeps their intent and changes these:

| Requirements sketch | Here | Reason |
|---|---|---|
| `task` (custom queue) | `sync.stream_run` plus Absurd | PD-1 |
| `records_seen` | `seen_gen` column | PD-5 |
| `record_count` | `data.stream_head` | Same row also holds the monotonic clock |
| `invite_token`, `oauth_session` | `connect_session`, `oauth_state` | Renamed to match what the dashboard and connect UI call them |
| `credential.ciphertext` (AES-GCM, shared key) | `sealed` (sealed box) | PD-4 |
| no `integration`, no `vendor_app` | both added | PD-3, PD-10 |
| no per-stream grant table | `connection_grant` | AUTH-08 needs a place to live |
| `outbox_event`, `webhook_endpoint`, `webhook_delivery` | Same, in `events`, plus `webhook_attempt` | Part 7 |
