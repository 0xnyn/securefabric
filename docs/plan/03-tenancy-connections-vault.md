# Part 3: Tenancy, access, vault and connections

## 1. Tenancy

```
Account ── one WorkOS organization, the billing entity
  └─ Environment ── isolation boundary: keys, data, webhooks, vault key (TEN-02)
       ├─ Integration ── a connector enabled and configured here
       └─ Organization ── the customer's end customer
            └─ Connection ── one vendor tenant, through one integration
```

The environment is the unit of isolation. Every API key belongs to one environment, every tenant row carries its id, and row-level security is keyed on it. An id from another environment is indistinguishable from an id that does not exist, so cross-environment access returns 404, never 403 (TEN-02's acceptance test).

A new account gets two environments, `dev` and `prod`, matching the dashboard's seed.

## 2. Dashboard users: WorkOS, kept basic

Scope for this plan is deliberately small.

- **Sign-in.** WorkOS AuthKit hosted login. The dashboard (`apps/dash`) uses the WorkOS Next.js integration for the session cookie and forwards the access token to the API as a bearer token.
- **API verification.** The API validates the WorkOS access token against WorkOS's JWKS (cached), reads the user id and organization id from its claims, and maps them to `app_user` and `account`. Rows are created on first sight (just-in-time provisioning).
- **Account creation.** A first sign-in with no WorkOS organization creates one, plus the account, an admin membership and the two environments.
- **Invites.** WorkOS invitations. Membership role is stored on our side.
- **Environment selection.** A session is not bound to an environment, so session-authenticated requests carry `X-Environment-Id` (the dashboard sets it from the URL slug). The API checks that the environment belongs to the session's account.

Deferred, and cheap to add later because WorkOS owns them: SSO and SCIM (TEN-10), enforced MFA (TEN-11), and fine-grained role enforcement (TEN-09). The `membership.role` column and a single `require_role()` dependency exist from the start, so tightening RBAC later changes one function and a route table, not the schema.

## 3. API keys

- Format: `sfk_<live|test>_<region>_<43 random base62 characters>`. The region segment lets a wrong-region request be rejected before any lookup (API-10), and the recognisable prefix lets secret scanners find leaked keys.
- Stored as an HMAC-SHA256 under a server pepper. The full key is returned once, at creation.
- Scopes per key (TEN-07). A missing scope returns 403 naming the scope.
- Several live keys per environment (TEN-08). Rotation is create, deploy, revoke.
- Revocation takes effect within 60 seconds: the API caches key lookups for at most 30 seconds.
- Accepted in `Authorization: Bearer` and, for Leen clients, `X-API-KEY`.

## 4. The principal

Both authenticators produce the same object, and nothing below the dependency layer knows which was used:

```
Principal(kind = api_key | user, account_id, environment_id, scopes, actor_id)
```

A user principal's scopes are derived from its role. Every domain call takes the principal, opens `tenant_tx(principal.environment_id)`, and writes an audit event for mutating calls (SEC-08).

## 5. Vault

### Key hierarchy

```
KEK (KeyProvider: local master key in dev, cloud KMS in production)   ← worker roles only
  └─ wraps → environment private key (X25519)      stored in control.environment
                 pairs with → environment public key   readable by the API
                                └─ seals → credential.sealed, credential.token_sealed,
                                           vendor_app.secrets_sealed, webhook endpoint secrets

Ingress key (symmetric, held by the API)
  └─ encrypts → vendor_app.ingress_secret_enc (inbound webhook secrets only)

Platform key pair (for platform-owned vendor apps)
  └─ seals → the shared GitHub App's private key
```

### Rules

- **Seal on arrival.** A credential in a request body is validated against the connector's credential schema, sealed, and the plaintext dropped before the handler returns. It is never logged: request bodies on credential routes are excluded from access logs, and the structured logger redacts by field name and by pattern (SEC-07).
- **Bind on open.** The sealed plaintext is an envelope `{v, environment_id, connection_id, purpose, payload}`. The worker checks the envelope against the row it was read from and refuses a mismatch, so ciphertext copied to another connection is useless (SEC-02).
- **Write-only.** No endpoint returns credential material. `GET /connections/{id}` has no `credentials` field. The dashboard shows which fields are set and when they were last rotated (AUTH-09).
- **Rotation.** `vault_key_version` on the environment and on each sealed row. Rotating generates a new key pair, and a background task re-seals rows. Both versions open during the transition. Nango refuses encryption-key rotation outright, which is the cautionary example.
- **Crypto-shredding.** Deleting an environment destroys its wrapped private key, which makes any leftover ciphertext, including in backups, unreadable (D8).

### Token providers

Every connector's auth resolves to a `TokenProvider` in the CDK with one method, `get(ctx) -> AuthMaterial`. Implementations:

| Provider | Used by | Behaviour |
|---|---|---|
| `StaticSecret` | API key and basic auth | Returns the sealed secret |
| `OAuth2Refresh` | Three-legged OAuth | Refreshes with the refresh token, handles single-use refresh tokens |
| `ClientCredentials` | OAuth2 client credentials | Mints and caches |
| `GitHubApp` | GITHUB | Signs an app JWT, exchanges for an installation token, caches it |
| `AwsAssumeRole` | Reserved | Interface only in this plan |

All of them share one refresh discipline (AUTH-05, AUTH-06):

1. Use the cached token if it has more than 15 minutes left (10 for GitHub's one-hour tokens).
2. Otherwise take a per-connection advisory lock, re-read the row, and refresh only if still needed. Fifty concurrent readers cause one vendor call.
3. On failure, wait at least 30 seconds before another attempt, count failing days once per calendar day, mark `refresh_exhausted` after 4, and emit a health change on the first failure and on recovery.
4. A background task refreshes tokens that have not been refreshed for 24 hours, so a broken credential is discovered before the next scheduled sync.

GitHub exercises the lock, the cache and the failure policy. SANDBOX exercises refresh tokens and client credentials.

## 6. Connection lifecycle

### States

```
            verify ok                pause                 delete
 PENDING ─────────────► ACTIVE ◄──────────────► PAUSED ─────────────► DELETED ──(30 days)──► HARD_DELETED
    │                     │        resume                               ▲
    │ verify fails        └─────────────────────────────────────────────┘
    ▼                                   delete
 stays PENDING with health detail, or DELETED if abandoned for 7 days
```

The transition table is data in `packages/domain/connections`. An illegal transition returns 409 (CON-02).

- **Create** (CON-01). `POST /v1/organizations/{id}/connections` with `vendor` or `integration`, `credentials`, `options`, `identifier`. Returns `PENDING` at once and enqueues `connection.verify`. For redirect-based connectors (GitHub) the response carries an `authorize_url` instead of taking credentials.
- **Verify** (AUTH-07, AUTH-08). A control-worker task calls the connector's `verify()`, then `probe()` for each enabled stream, writes `connection_grant` rows, computes the tenant fingerprint, checks for a duplicate (AUTH-10), and moves to `ACTIVE`. The connection is active even if some streams are not granted. Health then reports `UNAUTHORIZED` with the affected streams in `details`.
- **Test** (CON-11). `GET /v1/connections/{id}/test` spawns the same verify task and waits up to 30 seconds for its result. A vendor rejection is a 200 with `is_valid: false`.
- **Rotate credentials** (AUTH-11). `PATCH` seals the new credentials into a staging column, verifies them, and swaps only on success. A failed verification leaves the old ones syncing.
- **Re-authorise** (CON-09). A connect session created with a `connection_id` runs the connect flow again and updates the same connection. Ids, history and data are unchanged.
- **Pause and resume** (CON-03). Pausing sets schedules to `PAUSED`, lets a running stream run finish its current page and stop, and keeps data readable. Resuming re-enables schedules and queues one catch-up job.
- **Delete** (CON-04). In one transaction: state to `DELETED`, credential row deleted, schedules deleted, `purge_after` set to 30 days out, `connection.deleted` written to the outbox. Data calls return 404 from that moment because every data query joins on a live connection. A maintenance task hard-deletes the data on day 30 and sets `HARD_DELETED`.
- **Options** (CON-05). Validated against the manifest's JSON Schema. Platform-level options every connector gets: per-stream interval, `initial_lookback_days`, `severity_floor`, `external_use_only` (CON-16). An interval above a stream's declared vendor retention is rejected (SYNC-18).

### Organization deletion
Returns 409 while the organization has a connection in `PENDING`, `ACTIVE` or `PAUSED` (TEN-03).

## 7. Health

Health is orthogonal to state. It is an object on the connection (CON-12):

```json
{
  "name": "UNAUTHORIZED",
  "status": "UNHEALTHY",
  "description": "GitHub denied access to Dependabot alerts.",
  "resolution_owner": "CUSTOMER",
  "details": [{"data_export_type": "dependabot_alerts", "endpoint": "GET /orgs/{org}/dependabot/alerts", "reason": "permission_missing"}]
}
```

| Code | Status | Owner | Raised when |
|---|---|---|---|
| `INITIALIZING` | INITIALIZING | PLATFORM | No stream has completed a first full pass yet |
| `HEALTHY` | HEALTHY | none | Every enabled, granted stream's last run succeeded |
| `UNAUTHORIZED` | UNHEALTHY | CUSTOMER | Credentials rejected, app uninstalled or suspended, or a stream's permission is missing |
| `RATE_LIMIT_EXCEEDED` | UNHEALTHY | VENDOR | A run could not finish inside its deadline because of vendor throttling |
| `VENDOR_CLIENT_ERROR` | UNHEALTHY | CUSTOMER | A 4xx we cannot classify further |
| `VENDOR_SERVER_ERROR` | UNHEALTHY | VENDOR | 5xx after all retries |
| `EXECUTION_TIMEOUT` | UNHEALTHY | PLATFORM | Run deadline exceeded |
| `CONFIGURATION_ERROR` | UNHEALTHY | CUSTOMER | Invalid options or base URL (our addition) |
| `REAUTHORIZATION_REQUIRED` | UNHEALTHY | CUSTOMER | Token refresh exhausted (our addition) |
| `INTERNAL_ERROR` | UNHEALTHY | PLATFORM | Anything unclassified. Pages on-call. |

Rules:

- Every stream run ends with exactly one code. The connection's health is the worst code across the latest run of each enabled stream, with a fixed severity order.
- A health change writes a `connection_health_event` row and an outbox event in the same transaction, so every transition produces exactly one `connection.health.changed` event (HOOK-01).
- A stream whose feature is not enabled at the vendor (`NOT_ENABLED` grant) does not make the connection unhealthy. It appears in `details` with `reason: "feature_not_enabled"` under a `HEALTHY` code. This is the difference between "GitHub denied us" and "this repository has no code scanning", which customers need to tell apart.
- Each code has a runbook (OPS-06), linked from the admin console.

## 8. Connect flow

The connect flow is how an end user authorises a connection without the customer handling credentials. One flow serves the embedded UI (CON-07) and the hosted link (CON-08).

```
customer backend                 connect UI (apps/dash /connect/[token])            API                         vendor
      │  POST /v1/connect_sessions        │                                          │                            │
      │──────────────────────────────────────────────────────────────────────────────►│ create session (30 min)    │
      │◄───────────── {token, url} ───────────────────────────────────────────────────│                            │
      │   give url or token to the end user                                           │                            │
      │                                   │ GET /v1/connect/session (Bearer token)    │                            │
      │                                   │──────────────────────────────────────────►│ integrations, schemas      │
      │                                   │  render picker or form from JSON Schema   │                            │
      │                                   │ POST /v1/connect/connections              │                            │
      │                                   │──────────────────────────────────────────►│ create PENDING connection  │
      │                                   │                                           │ seal credentials, or       │
      │                                   │◄──────── {authorize_url} or {status} ─────│ create oauth_state         │
      │                                   │ redirect ─────────────────────────────────────────────────────────────►│
      │                                   │                                           │◄── callback with state ────│
      │                                   │◄──────── redirect to success or error ────│ bind, enqueue verify       │
      │                                   │ poll GET /v1/connect/connections/{id}     │                            │
      │◄── webhook connection.create.succeeded ───────────────────────────────────────│                            │
```

- The session token is a bearer credential scoped to one organization and a list of integrations, valid for 30 minutes, stored hashed, single use for creation (reuse or expiry returns 410).
- Forms are rendered from the connector's credential and option schemas with no connector-specific UI code (CAT-04). GitHub has no form at all, only a button.
- The connector's permission guide is shown inline (CAT-05).
- Success and error redirect targets must match the environment's allowed origins.
- The embed is an iframe of the hosted page, opened by `packages/connect-js`, which relays `success`, `error` and `close` by `postMessage` with an origin check. Theming (colour, logo, dark mode) is read from `environment.settings`.

The GitHub-specific half of this flow, including how an installation is safely bound to a tenant, is in part 6, section 3.
