# Part 7: Public API and events

## 1. Shape

- Base path `/v1`. Everything is in one version: provisioning, data, jobs, webhooks (API-11). The current `/api/v1` prefix is dropped.
- One surface for customers and the dashboard. Authentication is an API key (`Authorization: Bearer sfk_...` or `X-API-KEY`) or a WorkOS session token with `X-Environment-Id`.
- JSON bodies are snake_case with Leen V2 field names. Query parameters keep Leen's spelling, including camelCase ones such as `updatedSince`.
- Every response carries `X-Request-Id`.
- OpenAPI 3.1 is generated from the Pydantic models, committed, and diffed in CI. A removed field or a changed type fails the build (API-14, NORM-11). The TypeScript client is generated from it as today.
- Enumerations are open: clients must tolerate unknown values. This is stated in the docs and in the generated SDK types.

## 2. Endpoints

### Catalogue
| Method and path | Auth | Notes |
|---|---|---|
| `GET /v1/connectors` | None | Public list: id, name, categories, auth modes, credential schema, data types, docs and logo URLs (CAT-01) |
| `GET /v1/connectors/{id}` | None | |
| `GET /v1/integrations` | Key | Enabled connectors in this environment with version, deprecated flag, option schema and the capabilities block (CAT-02) |
| `POST, PATCH, DELETE /v1/integrations/{id}` | Key | |
| `GET, POST, PATCH, DELETE /v1/vendor_apps` | Key | Customer-owned app registrations. Secrets are write-only. |

### Provisioning
| Method and path | Notes |
|---|---|
| `POST, GET /v1/organizations` | Filters `name`, `identifier`, `id`, `search` (TEN-04) |
| `GET, PATCH, DELETE /v1/organizations/{id}` | Delete returns 409 with active connections |
| `POST /v1/organizations/{id}/connections` | CON-01 |
| `GET /v1/connections` | Filters: `organizationId`, `vendor`, `state`, `healthStatus`, `healthStatusCodes`, `tags[key]=value` (CON-13, TEN-05) |
| `GET, PATCH, DELETE /v1/connections/{id}` | PATCH covers state (pause, resume), options, credentials, tags |
| `PUT, PATCH /v1/connections/{id}/metadata` | Replace or merge, 16 KB cap (CON-10) |
| `GET /v1/connections/{id}/test` | CON-11 |
| `GET /v1/connections/{id}/health/history` | CON-14 |
| `POST /v1/connect_sessions` | Creates the invite token and hosted URL |
| `GET /v1/connect_sessions` | Shows `expires_at` and `used_at`, never the token |

### Connect flow (session-token authenticated)
`GET /v1/connect/session`, `POST /v1/connect/connections`, `GET /v1/connect/connections/{id}`, `GET /v1/connect/callback/{connector}`.

### Jobs
| Method and path | Notes |
|---|---|
| `POST /v1/connections/{id}/jobs` | On-demand. Body: `streams`, `force_full_refresh`, `since` (SYNC-06) |
| `GET /v1/connections/{id}/jobs` | Filters `status`, `type`, `startedAtSince` |
| `GET /v1/jobs/{id}` | With per-stream results |
| `POST /v1/jobs/{id}/cancel` | SYNC-13 |
| `POST /v1/connections/{id}/reset` | SYNC-14 |
| `GET /v1/jobs/{id}/logs` | OBS-01 |

### Data
| Method and path | Notes |
|---|---|
| `GET /v1/resources`, `GET /v1/resources/{id}` | |
| `GET /v1/vulnerability_findings`, `GET /v1/vulnerability_findings/{id}` | |
| `GET /v1/vulnerability_findings/{id}/history` | State history |
| `GET /v1/enrichments/cves/{id}` | ENR-04 |

### Actions, webhooks, keys, observability
| Method and path | Notes |
|---|---|
| `POST /v1/vulnerability_findings/{id}/actions` | Write-back, section 7 |
| `GET /v1/actions/{id}` | |
| `GET, POST, PATCH, DELETE /v1/webhook_endpoints` | Plus `/rotate_secret`, `/ping` |
| `GET /v1/webhook_endpoints/{id}/deliveries`, `POST /v1/webhook_deliveries/{id}/replay` | HOOK-06 |
| `GET /v1/events` | The outbox as a pull feed, for customers who cannot receive webhooks |
| `GET, POST, DELETE /v1/api_keys` | TEN-06 |
| `GET /v1/operations` | Customer-visible logs |
| `GET /v1/usage` | BILL-03, read-only counters |

### Session only
`GET /v1/me`, `GET, POST /v1/environments`, `GET, POST, PATCH, DELETE /v1/members`, `GET /v1/audit_events`.

### Vendor ingress
`POST /v1/ingress/{connector}/{vendor_app_id}`. Signature-authenticated, not in the public OpenAPI.

## 3. Data scoping

A data request names its scope with exactly one header:

- `X-CONNECTION-ID`: one connection (Leen-compatible). The query touches one partition.
- `X-ORGANIZATION-ID`: every connection of that organization, with an optional `connectionId` filter. Each record carries `connection_id` (TEN-12).

Neither header, or both, is a 400. A connection in `DELETED` state is a 404.

## 4. Pagination and incremental reads

**Keyset only.** `limit` 1 to 500, default 100. Responses are `{items, next_cursor, previous_cursor}` (API-02).

**The cursor** is an opaque, signed, versioned token encoding the sort key of the last row, the sort direction, a hash of the active filters, and the scope. Signing means a tampered cursor is a 400, not a strange query.

**`updatedSince` with a cursor.** Leen returns 422 if both are sent. Here the filter set travels inside the cursor, so resending the same `updatedSince` alongside it is accepted, and sending a different filter set than the cursor was created with is a 400 that says which parameter conflicts (API-03).

**Default order** is `(updated_at, id)` ascending. That is the incremental feed: a client stores the last `next_cursor`, or the largest `updated_at` it saw, and resumes from it. Because of how `updated_at` is assigned (part 4, section 7), this never skips a change within a connection. Organization-scoped reads hide rows younger than 5 seconds.

**Deletes are in the feed** (CDC-02). Deleted records are returned by incremental queries with `state: "DELETED"` and `deleted_at` for 90 days, then purged. A plain listing without `updatedSince` excludes them unless `state=DELETED` is requested.

**`changeType`** filters an incremental read to `added`, `updated` or `deleted` (CDC-03), derived from `created_at = updated_at` and `deleted_at`.

**Sorting** (API-12). `sort=field[:asc|:desc]` on `severity`, `updated_at`, `state_updated_at`, `first_seen`, `last_seen`. Every sort has `id` as a tiebreaker, so pages are stable.

## 5. Filters

Every Leen V2 filter is supported (API-01).

| Endpoint | Filters |
|---|---|
| Resources | `name`, `vendor`, `state`, `type`, `updatedSince`, `ids` |
| Findings | `severity`, `state`, `type`, `has_fix`, `reachability`, `exploitable`, `firstSeenSince`, `lastSeenSince`, `stateUpdatedSince`, `updatedSince`, `resourceId`, `ids` (at most 100), `cveId`, `changeType` |

Rules:

- Comma-separated values are OR within a filter. Filters combine with AND.
- Unknown parameters are a 400 naming the parameter (API-05).
- Tri-state filters (`has_fix`, `exploitable`) accept `true` or `false`. A record with null matches neither. Passing null is a 422, as in Leen.
- A filter the connection's connector cannot honour is not an error. The response carries `X-Unsupported-Filters: reachability`, computed from capabilities, so a client can tell "no matches" from "this vendor never says".
- `include=resources` embeds full resource objects in findings (API-13). Without it, `resources` carries ids and names.

## 6. Response shapes

The finding and resource bodies are Leen V2's (part 2, section 4, lists every field). Our additions are all additive:

- `connection_id`, `organization_id` on every record.
- `created_at`, `updated_at`, `deleted_at`.
- `_meta: {derived: [...], stream, connector_version}`.
- `enrichment: {nvd, kev, epss}` on findings, marked as ours. Vendor-supplied values always take precedence in `vulnerabilities[]` (ENR-05).

**Enrichment is joined at read time** in the first release. The API looks up `cve_ids` in the global `data.cve` mirror when building the response, so a new KEV listing appears on every affected finding immediately, with no fan-out rewrite of tenant rows and no flood of `updated_at` changes. The cost is that enrichment changes do not appear in the incremental feed. If customers need that, a later release materialises enrichment onto the row behind a per-environment flag.

## 7. Actions

`POST /v1/vulnerability_findings/{id}/actions` with `{action: "set_state", state: "IGNORED", reason: "accepted_risk", comment}`.

- Requires the `actions:write` scope, an integration with write-back enabled, and a connector that declares the action.
- Requires `Idempotency-Key`. A repeat returns the first result (ACT-03).
- Runs as a control-worker task. The response is 202 with an action id. `GET /v1/actions/{id}` reports `PENDING`, `SUCCEEDED` or `FAILED` with the vendor's answer. Synchronous wait up to 30 seconds is available with `Prefer: wait=30`.
- On success the record is marked dirty and re-fetched, and an `action.completed` event is emitted.
- Reasons are a small canonical set (`false_positive`, `accepted_risk`, `test_code`, `revoked`), mapped per connector. A reason the vendor cannot express is a 422 listing the ones it can.

## 8. Errors, limits, idempotency

**Errors** are RFC 9457 problem details (API-06):

```json
{
  "type": "https://docs.securefabric.dev/errors/scope_missing",
  "title": "Missing scope",
  "status": 403,
  "detail": "This key lacks provisioning:write.",
  "code": "scope_missing",
  "request_id": "req_...",
  "errors": [{"field": "...", "message": "..."}]
}
```

`code` is a stable machine-readable string. The existing envelope (`{"error": {...}}`) and the client's `unwrap()` helper change to this shape in one step. FastAPI's default 422 body is replaced by the same shape so there is exactly one error format, where Leen mixes two.

**Rate limits** (API-07). A token bucket per environment, default 1,000 requests a minute, with `X-RateLimit-Limit`, `-Remaining`, `-Reset` on every response and 429 with `Retry-After`. Counters are in process memory and synchronised through Postgres every second, which is approximate across API instances but needs no extra infrastructure. The limiter is behind an interface in case that stops being good enough.

**Idempotency** (API-08). `Idempotency-Key` on any POST. The first request stores its response, and a replay within 24 hours returns it with `Idempotent-Replayed: true`. A replay with a different body is a 422.

**Deprecation** (API-09). Deprecated operations send `Deprecation` and `Sunset` headers, driven by an annotation on the route.

## 9. Events and outbound webhooks

### Outbox

An event is a row in `events.outbox_event`, inserted in the same transaction as the change it describes (HOOK-04, D7). No code path sends a webhook directly. If the transaction commits, the event exists, and if it rolls back, it does not.

The scheduler's dispatch step reads undispatched rows in id order, creates one `webhook_delivery` per subscribed, enabled endpoint, spawns a delivery task for each, and marks the event dispatched. Nango sends webhooks fire-and-forget after the fact, which is the gap this closes.

### Envelope (HOOK-10)

```json
{
  "id": "evt_...",
  "type": "sync.completed",
  "created_at": "2026-12-01T10:15:00.000Z",
  "environment_id": "...",
  "organization_id": "...",
  "connection_id": "...",
  "sequence": 4182,
  "data": { }
}
```

`sequence` increases strictly per connection. Delivery order is not guaranteed, and the sequence lets a consumer detect and repair reordering (HOOK-11).

### Catalogue (HOOK-01)

| Event | When |
|---|---|
| `connection.create.succeeded`, `connection.create.failed` | Verification finished (Leen-compatible names) |
| `connection.sync.succeeded`, `connection.sync.failed`, `connection.sync.unauthorized` | Job finished (Leen-compatible) |
| `sync.completed` | Job finished, with per-stream `added`, `updated`, `deleted` counts and the time window, so a consumer can skip pulling when nothing changed (CDC-04) |
| `connection.health.changed` | Every health transition, including ones we or the vendor own |
| `connection.paused`, `connection.resumed`, `connection.deleted` | |
| `action.completed`, `action.failed` | |
| `webhook.ping` | Endpoint test |

Record-level events (`finding.created` and similar, CDC-05) are reserved names and not emitted in this plan. The outbox can carry them, but they need volume caps first.

### Delivery

One Absurd task per delivery on the `delivery` queue. Durable sleeps between attempts fit this exactly.

- **Signing** (HOOK-03). Headers `SecureFabric-Timestamp` and `SecureFabric-Signature: v1=<hex>`, where the signature is HMAC-SHA256 over `"{timestamp}.{raw body}"`. Receivers reject timestamps more than 5 minutes off. For 24 hours after a secret rotation, both the old and new secrets sign and both signatures are sent. There is no bare-hash header: Nango still ships a length-extension-vulnerable one for backward compatibility, and we have no such history to honour.
- **Retries** (HOOK-05). 5xx, 408, 429 and network errors retry at 10 seconds, 1 minute, 5 minutes, 30 minutes, 2 hours, 6 hours, 12 hours and 24 hours, with jitter, then the delivery is `DEAD`. Other 4xx responses fail permanently. The request timeout is 15 seconds. Nango does not retry 429, and we do.
- **SSRF guard** (HOOK-08). HTTPS only, URL at most 2,048 characters, resolved addresses checked against the deny list before every attempt, connection made to the checked address.
- **Log and replay** (HOOK-06). Every attempt is recorded with status, latency and a truncated response. One delivery or a time range can be replayed, including dead ones.
- **Auto-disable** (HOOK-07). An endpoint failing continuously for 5 days is disabled and account admins are emailed. Its events stay available for replay.
- **Limits** (HOOK-02). At most 5 endpoints per environment, each subscribing to a list of event types.

### Pull alternative

`GET /v1/events?after=<cursor>` returns the same envelopes in id order. A customer behind a firewall, or one who distrusts webhooks, polls this instead, and it costs nothing extra because the outbox already exists.
