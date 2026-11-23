# Part 5: Connector development kit and the SANDBOX connector

The CDK is the contract between the platform and a connector. If it is right, connector number two is a week of mapping work. If it is wrong, every connector leaks into the platform.

## 1. What a connector is

A directory in `packages/connectors/`:

```
github/
  manifest.yaml        identity, auth, options, streams, limits, permissions
  connector.py         the Connector class: verify, probe, streams, actions, webhooks
  streams/             one module per stream: read, read_one, normalize
  mapping.py           severity and state tables as data
  fixtures/            recorded vendor responses, scrubbed
  golden/              expected normalised output per fixture
  docs.md              permission guide and notes, published to the docs site
```

A connector imports only `securefabric_cdk` and `securefabric_schema`. It has no database access, no vault access and no HTTP library of its own. Everything it does to the outside world goes through the context object it is handed. A lint rule fails CI on any other import (CDK-03).

## 2. The manifest

`manifest.yaml` is validated against a JSON Schema in CI (CDK-02). The catalogue (`control.connector`), the public connector list, the capabilities block, the connect forms and the docs are all generated from it. This replaces the hand-written `apps/dash/src/lib/catalog.ts` and its exported `catalog.json`.

```yaml
id: GITHUB
version: 1.0.0
display_name: GitHub Advanced Security
categories: [appsec]
status: beta

auth:
  mode: APP                      # APP | API_KEY | BASIC | OAUTH2 | OAUTH2_CC | AWS_ROLE
  vendor_app: required
  connect: redirect              # redirect | form

connection_config:               # non-secret, JSON Schema
  properties:
    installation_id: {type: integer, automated: true}
    account_login:   {type: string,  automated: true}

credentials: {}                  # JSON Schema with secret flags. Empty for GitHub.

options:                         # JSON Schema, drives forms and validation
  properties:
    secret_locations: {enum: [first, all], default: first}
    branch_scope:     {enum: [default, protected, all], default: default}
    include_archived: {type: boolean, default: true}

regions:                         # CAT-08
  - {id: github.com, api_base: "https://api.github.com"}
  - {id: ghe.com,    api_base: "https://api.{subdomain}.ghe.com"}
  - {id: ghes,       api_base: "https://{host}/api/v3"}

http:
  retry:
    statuses: [429, "5xx"]
    reset_header: x-ratelimit-reset
    retry_after_header: retry-after
    remaining_header: x-ratelimit-remaining
    body_patterns:
      - {status: 403, contains: "secondary rate limit", treat_as: rate_limited}
      - {status: 403, contains: "rate limit exceeded",  treat_as: rate_limited}
  budget:
    key: "{vendor_app_id}:{installation_id}"
    per_hour: 5000
    per_minute_points: 900
    max_concurrency: 4

permissions:                     # CAT-05, SEC-09. Checked against streams in CI.
  - {name: "Code scanning alerts", access: read, streams: [code_scanning_alerts]}
  - {name: "Secret scanning alerts", access: read, streams: [secret_scanning_alerts]}
  - {name: "Dependabot alerts", access: read, streams: [dependabot_alerts]}
  - {name: "Metadata", access: read, streams: [repositories, branches]}

streams:
  - name: dependabot_alerts
    object: vulnerability_finding
    finding_types: [DEPENDENCY]
    sync_mode: incremental       # incremental | full | export
    interval: {default: 3600, min: 900, max: 86400}
    full_every: 604800
    vendor_retention: null       # seconds. Intervals above it are rejected (SYNC-18).
    deletion: vendor_reported    # vendor_reported | sweep | none
    natural_key: "dependabot:{repository.id}:{number}"
    checkpoint_schema: {...}
    webhook_events: [dependabot_alert]
    capabilities:
      severity:     {supported: true}
      has_fix:      {supported: true}
      exploitable:  {supported: false, notes: "GitHub makes no exploitability assertion"}
      reachability: {supported: false}

actions:
  - name: finding.set_state
    object: vulnerability_finding
    requires_permission_tier: read_write
```

The `capabilities` block declares what is supported. The `values_emitted` part of the public capabilities response is not written by hand: CI computes it from the golden output of the fixtures and fails if the manifest claims a value no fixture produces (CAT-03).

## 3. The interface

```python
class Connector(Protocol):
    manifest: Manifest

    async def verify(self, ctx: Context) -> VerifyResult: ...
        # One cheap call proving the credential works. Returns the vendor tenant
        # identity used for the duplicate-connection fingerprint.

    async def probe(self, ctx: Context, stream: str) -> Grant: ...
        # Can this credential read this stream? GRANTED | UNAUTHORIZED | NOT_ENABLED | UNSUPPORTED

    def stream(self, name: str) -> Stream: ...

    async def handle_webhook(self, delivery: IngressDelivery) -> list[WebhookEffect]: ...
        # Pure function of the payload: no I/O. Returns effects such as
        # MarkDirty(stream, key), TriggerStream(stream), ConnectionRevoked(), Ignore().

    async def perform(self, ctx: Context, action: Action) -> ActionResult: ...


class Stream(Protocol):
    async def read(self, ctx: Context, checkpoint: Checkpoint, mode: Mode) -> AsyncIterator[Page]: ...
        # Yields pages. Each page carries raw items and the checkpoint value to save with it.

    async def read_one(self, ctx: Context, key: str) -> RawItem | Gone: ...
        # For targeted refresh.

    def normalize(self, raw: RawItem, ctx: NormalizeContext) -> Record | Skip: ...
        # Pure. No I/O. Deterministic. This is what golden tests pin.
```

Design rules behind this shape:

- **`normalize` is pure.** It takes one raw item and returns one canonical record or a skip. No network, no clock, no randomness. That is what makes fixtures, golden tests, re-normalisation and sandbox connections all work from the same recorded bytes.
- **`read` owns pagination and checkpoints, and nothing else.** It decides what to ask the vendor next and what to save. It never writes.
- **`handle_webhook` is pure too.** The connector says what a delivery means, and the platform does it. A connector cannot write data from a webhook even by mistake (PD-11).
- **The platform derives what is common.** Ids, hashes, `REOPENED`, `state_updated_at`, stub resources, `first_seen_at`, severity floor. Connectors that reimplement these diverge.

### The context

`Context` is everything a connector may touch:

| Member | What it gives |
|---|---|
| `ctx.http` | The one HTTP client: auth injection, base URL, rate budget, retries, egress policy, raw capture, operation log lines |
| `ctx.paginate` | Link-header, cursor, page-token and offset helpers |
| `ctx.config`, `ctx.options` | The connection's non-secret config and validated options |
| `ctx.log` | Structured, redacted logger, written to the customer-visible operation log |
| `ctx.now()` | The clock, injectable in tests |
| `ctx.deadline` | Remaining time for the slice |

There is no `ctx.db` and no `ctx.credentials`. The HTTP client injects auth itself, so connector code never holds a token.

### Errors

A closed set, mapped to outcomes in part 4, section 5: `AuthRejected`, `PermissionMissing(stream)`, `FeatureNotEnabled(stream)`, `RateLimited(reset_at)`, `VendorUnavailable`, `VendorRejected`, `ConfigInvalid`, `Gone`. The HTTP client raises most of them from the manifest's retry policy. Connectors raise the rest where only they can tell, for example distinguishing GitHub's "Advanced Security must be enabled" from a real permission error.

## 4. Testing a connector

| Layer | What it proves | When it runs |
|---|---|---|
| **Fixture replay** (CDK-04) | `read` paginates correctly and saves resumable checkpoints | Every commit |
| **Golden output** (CDK-05) | `normalize` output for each fixture is exactly the committed snapshot. A mapping change shows up as a diff in review. | Every commit |
| **Canonical validation** | Every golden record validates against `packages/schema` | Every commit |
| **Conformance suite** | Platform-level properties for any connector, section 5 | Every commit |
| **Dry run** (CDK-06) | `securefabric-cdk dryrun GITHUB --connection <id> --stream dependabot_alerts` runs against a live connection, persists nothing, prints normalised output and a capability report | On demand |
| **Nightly live sync** (CDK-07) | A real sync against the seeded test tenant. Diffs vendor field sets and record counts against the previous night and opens an issue on drift. | Nightly |

**Recording.** `securefabric-cdk record` runs a stream against a test tenant through a recording transport and writes each response to `fixtures/` after scrubbing: authorization headers, tokens, anything matching a secret pattern, and connector-declared sensitive fields (for GitHub, the `secret` field of secret scanning alerts). A CI check scans fixtures for secret patterns.

**Coverage report** (CDK-09). CI computes, per connector and stream, the share of canonical fields filled across fixtures. It is published in the docs and feeds capabilities.

**Scaffold** (CDK-08). `securefabric-cdk new <VENDOR>` creates the directory, a manifest stub, a stream stub, a test file and a docs stub.

**Review checklist** (CDK-10). The pull request template for a connector asks for the natural key and why it is stable, the deletion mode, the severity and state tables, the rate policy, and the permissions.

## 5. The conformance suite

A parametrised test suite in the CDK that every connector must pass. It runs the real engine against the connector with a replaying transport. These are the properties that otherwise get rediscovered as production incidents:

1. **Idempotent.** Syncing the same fixtures twice writes zero rows the second time and moves no `updated_at`.
2. **Resumable.** Killing the run after every possible page boundary, then resuming, produces the same final record set as an uninterrupted run.
3. **Stable ids.** The same vendor record has the same id across runs, resets and re-authorisation.
4. **Sweep-correct.** Removing an item from the fixtures and running a full pass deletes exactly that record. Interrupting and resuming that pass deletes exactly the same.
5. **Guarded.** A full pass that returns an empty listing deletes nothing and raises the sweep alert.
6. **Tri-state honest.** A stream that declares `exploitable: supported: false` emits null for every record (NORM-06).
7. **Never fabricates.** No canonical field is set when the corresponding vendor field is absent from the fixture, unless it is listed in `meta_derived` (NORM-09).
8. **Classified.** Injected 401, 403, 404, 429 and 500 responses each end in the expected health code.
9. **Linked.** Every finding references at least one resource that exists.
10. **Bounded.** Request count for an incremental run of an unchanged tenant is at most 5% of the backfill's (SYNC-03).
11. **Quiet.** No log line or operation record contains a credential or a scrubbed field.

## 6. The SANDBOX connector

SANDBOX is a first-party connector whose "vendor" is a deterministic generator running in-process behind the same HTTP client interface. Given a seed, it presents a vendor API with resources, findings, pagination, rate limits, auth and failures. It has three jobs.

**It exercises what GitHub does not.**

| Primitive | GitHub | SANDBOX |
|---|---|---|
| App installation auth | Yes | |
| API key and basic auth | | Yes |
| OAuth2 authorization code with refresh, including single-use refresh tokens | | Yes |
| OAuth2 client credentials | | Yes |
| Credential form rendered from schema | | Yes |
| Link-header pagination | Yes | |
| Offset and page-token pagination | | Yes |
| Incremental by sorted listing with a watermark | Yes | |
| Incremental by `since` filter | | Yes |
| Async export with polling and chunks | | Yes |
| Full-refresh stream with sweep | Yes (repositories) | Yes |
| `vendor_reported` deletion | Yes | Yes |
| Vendor retention shorter than the interval | | Yes |
| HOST, IMAGE and CONTAINER findings, all enum values | | Yes |
| Tri-state `exploitable` and `reachability` populated | | Yes |
| Inbound webhooks | Yes | Yes |
| Write-back action | Yes | Yes |
| Regional base URLs | Yes | Yes |

**It is the failure laboratory.** The generator accepts a scenario: return 429 with a reset 20 minutes out, fail every third page with a 500, revoke the token mid-run, return an empty listing, expire an export, deliver webhooks out of order. Engine tests for parking, backoff, health classification and the sweep guard are written against these scenarios and run in seconds with no network.

**It provides sandbox connections** (TEN-13). A customer can create a SANDBOX connection in any environment and get realistic synthetic data covering every enum value, to build against before connecting a real tenant. For a real connector, a sandbox connection (`is_sandbox = true`) replays that connector's recorded fixtures through the same pipeline, so a GitHub sandbox connection returns GitHub-shaped data.

SANDBOX is a real connector in the catalogue, flagged so it never counts toward billing.

## 7. What adding a connector looks like afterwards

1. `securefabric-cdk new TENABLE`.
2. Fill in the manifest: auth mode, credential schema, streams, limits, permissions.
3. Write `read` and `normalize` per stream and the mapping tables.
4. Record fixtures from a test tenant and commit the golden output.
5. Pass the conformance suite.
6. Write `docs.md`.

No migration, no API change, no dashboard change, no scheduler change. If step 2 or 3 needs something the CDK lacks, that is a platform gap, and the rule is to add it to the CDK and to SANDBOX, never to work around it inside the connector.
