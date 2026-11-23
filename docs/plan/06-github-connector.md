# Part 6: The GitHub connector

Scope: everything GitHub Advanced Security exposes as alerts (code scanning, secret scanning, Dependabot), the repositories and branches they attach to, coverage (which features are enabled where), on github.com, GHE.com and GitHub Enterprise Server, with near-real-time updates from webhooks and state write-back.

Facts here come from the research notes and a pass over docs.github.com. Anything that pass could not confirm is marked **(verify)** and collected as spikes in part 10, section 6. Each has a stated fallback, so no spike can block the design.

## 1. Product surface

| GitHub product | What we sync | Canonical object |
|---|---|---|
| Code scanning (CodeQL and third-party SARIF) | Alerts | Finding, type `CODE` |
| Secret scanning (Secret Protection) | Alerts and their locations | Finding, type `SECRET` |
| Dependabot alerts | Alerts | Finding, type `DEPENDENCY` |
| Repositories | Repositories in the installation, with security feature status | Resource, type `REPOSITORY` |
| Branches | Default branch always, more by option | Resource, type `BRANCH` |

Licensing reality the connector must handle gracefully: code scanning and secret scanning are free on public repositories and need paid add-ons on private ones, while Dependabot alerts are free everywhere. So a single organization routinely has features enabled on some repositories and not others. That is normal, and it must never read as a failure.

## 2. The GitHub App

### Registrations (`control.vendor_app`)

| Registration | Owner | Use |
|---|---|---|
| SecureFabric (read) | Platform, one per region | Default for github.com. One-click install. |
| SecureFabric (read and write) | Platform | Opt-in, for integrations with write-back enabled |
| Customer-owned | An environment | Required for GHES and GHE.com (an app is registered on the instance). Optional on github.com for customers who want their own name on the consent screen. |

SEC-09 requires read-only vendor access by default. Keeping write permissions in a separate app, instead of asking every customer for write access they may never use, satisfies that and still allows write-back.

### Permissions

| Permission | Access | Needed for |
|---|---|---|
| Metadata (repository) | Read | Repositories, branches. Mandatory for every app. |
| Code scanning alerts (repository) | Read | `code_scanning_alerts` |
| Secret scanning alerts (repository) | Read | `secret_scanning_alerts` |
| Dependabot alerts (repository) | Read | `dependabot_alerts` |
| Administration (repository) | Read | `security_and_analysis` on repositories, for coverage **(verify the minimum permission that returns this block)** |
| The three alert permissions | Write | Write-back app only |

The research card lists Contents read. The plan drops it: no stream reads file contents, and asking for code access we do not use would cost installs at security-conscious customers. If a later feature needs it (CODEOWNERS, SBOM), it becomes an optional permission.

### Webhook subscriptions

`code_scanning_alert`, `secret_scanning_alert`, `secret_scanning_alert_location`, `dependabot_alert`, `repository`, `security_and_analysis`, `installation_target`. The `installation` and `installation_repositories` events are delivered to every app without subscribing.

Webhook URL per registration: `https://<api host>/v1/ingress/github/<vendor_app_id>`.

## 3. Installing and binding an installation

This is the one place in the platform where a mistake lets one tenant read another's data, so it gets its own section.

**The hazard.** After installation GitHub redirects to our setup URL with `installation_id` in the query string. That value is not signed. Anyone can call the setup URL with someone else's installation id. With a shared app serving many tenants, trusting it would let tenant B bind tenant A's installation and read A's alerts.

**The rule.** An installation id is never trusted from a URL. It is bound to a connection only after GitHub itself confirms that the person in the browser can access that installation.

**The flow.**

1. The connect UI calls `POST /v1/connect/connections`. The API creates a `PENDING` connection and an `oauth_state` row and returns `authorize_url = <base_url>/apps/<slug>/installations/new?state=<state>`.
2. The user picks an account and repositories on GitHub and installs.
3. The app is configured with "Request user authorization (OAuth) during installation", so GitHub redirects to our callback with `code`, `installation_id`, `setup_action` and `state` **(verify the exact parameter set and that `state` is echoed)**.
4. The callback consumes `state` (single use, 10-minute expiry, bound to the connect session), exchanges `code` for a user access token, and calls `GET /user/installations`. The installation id from the URL must be in that list. If it is not, the flow ends in an error and the attempt is audit-logged.
5. The user token is discarded. It is never stored.
6. The connection gets `connection_config.installation_id`, the account login, id and type, and `vendor_tenant_ref`. `connection.verify` is enqueued.

**Edge cases.**

| Case | Handling |
|---|---|
| The app is already installed on that account | GitHub shows the configure page and may not redirect back. The connect UI offers "I already installed it", which runs a plain OAuth authorization, lists `GET /user/installations`, and lets the user pick one. Same verification, no reinstall. |
| The user is not an owner, so GitHub sends an install request to an owner (`setup_action=request`) | The connection stays `PENDING` with detail "waiting for an organization owner to approve". When the `installation` `created` webhook arrives, we match it to pending connections by the requester's login, as Nango does, but we do not bind on that alone: the connect UI shows "approved, click to finish", which runs the OAuth check. |
| The callback arrives with no `state` (installation started from GitHub's own UI) | Redirect to a generic page. Nothing is bound. |
| Two of our tenants connect the same GitHub organization through the shared app | Both connections reference the same installation. Each passed the OAuth check independently. They share one rate budget, which is why the budget key is the installation, not the connection. |
| The same organization is connected twice within one of our organizations | Rejected with 409 by the tenant fingerprint (`vendor_app_id`, GitHub account id). |
| Repository selection is "selected repositories" | Supported. The repositories stream reads what the installation can see. |
| Installation on a user account, not an organization | Supported through per-repository mode, section 6. |

## 4. Authentication at run time

`GitHubApp` token provider (part 3, section 5):

1. Open the app's private key from `vendor_app.secrets_sealed`. Worker only.
2. Sign a JWT (RS256, issuer is the app id, 9-minute expiry, issued-at backdated 60 seconds for clock drift).
3. `POST /app/installations/{installation_id}/access_tokens`. The token lasts one hour.
4. Cache it sealed in `credential.token_sealed`. Refresh when fewer than 10 minutes remain, single-flight under the connection's advisory lock.

Per-connection secret material is nothing at all: the connection holds an installation id, and the only secret is the app's key. Revoking access is the customer uninstalling the app.

Every request sends `X-GitHub-Api-Version` pinned in the manifest, and `Accept: application/vnd.github+json`.

## 5. Streams

| Stream | Object | Mode | Default interval | Deletion | Natural key |
|---|---|---|---|---|---|
| `repositories` | Resource `REPOSITORY` | Full | 1 hour | Sweep | `repo:<repository id>` |
| `branches` | Resource `BRANCH` | Full | 1 hour | Sweep | `branch:<repository id>:<branch name>` |
| `code_scanning_alerts` | Finding `CODE` | Incremental | 1 hour | Vendor-reported, weekly reconcile | `code_scanning:<repository id>:<alert number>` |
| `secret_scanning_alerts` | Finding `SECRET` | Incremental | 1 hour | Vendor-reported, weekly reconcile | `secret_scanning:<repository id>:<alert number>` |
| `dependabot_alerts` | Finding `DEPENDENCY` | Incremental | 1 hour | Vendor-reported, weekly reconcile | `dependabot:<repository id>:<alert number>` |

Interval bounds are 15 minutes to 24 hours. With webhooks on, the hourly schedule is a safety net and customers may lengthen it.

**Natural keys use the numeric repository id**, which survives renames and transfers. A key built on `owner/name` would orphan every finding when a repository is renamed.

**Alert numbers are per repository and per alert family**, which is why the family is in the key.

### `repositories`

- Endpoint: `GET /installation/repositories`, 100 per page **(verify)**. This is used instead of `GET /orgs/{org}/repos` because it returns exactly what the installation can access, works for user accounts, and respects "selected repositories". Fallback: `GET /orgs/{org}/repos`.
- Full pass every run. An organization with 5,000 repositories costs 50 requests.
- Sweep deletes repositories no longer visible. The sweep guard's vendor confirmation is the listing's own `total_count`.
- Archived repositories are kept, state `INACTIVE`. The `include_archived` option controls whether their alerts are synced.

### `branches`

- `branch_scope: default` (the default) emits one BRANCH resource per repository from the repository payload's `default_branch`, with no extra requests.
- `protected` and `all` call `GET /repos/{owner}/{repo}/branches` per repository, which costs at least one request per repository per run. Documented as expensive.
- Why default-only is the default: the organization-level code scanning listing reports alerts for the default branch only, and the other two alert families are not branch-scoped.

### The three alert streams

All three follow one pattern, implemented once in a shared base class.

**Listing mode.** Chosen per connection at verify time.

- `org` mode: `GET /orgs/{org}/code-scanning/alerts`, `/secret-scanning/alerts`, `/dependabot/alerts`. One listing covers every repository. Used for organization installations.
- `per_repo` mode: the repository-level endpoints, iterated over the repositories stream's output. Used for user-account installations, and as the fallback if the organization endpoints do not honour a selected-repositories installation **(verify)**.

**Backfill and full passes.** `sort=created&direction=asc&per_page=100`, no state filter (so every state is returned), following the `Link` header's cursor. Ascending by creation is stable while alerts are being created, since new ones land at the end. The checkpoint stores the resume cursor after every page. If GitHub rejects a stored cursor on resume, the pass restarts from the beginning with the same generation, which is safe because writes are idempotent.

**Incremental runs.** None of the three listings has a `since` filter. They do support `sort=updated&direction=desc`. So an incremental run walks newest-first and stops at the first alert whose `updated_at` is older than the checkpoint's watermark minus a 5-minute overlap.

```
checkpoint = { watermark: <timestamp>,                       # committed only when a walk completes
               walk: { target: <timestamp>, cursor: <opaque> } | null }   # an interrupted walk
```

- The watermark advances to the newest `updated_at` seen, and only when the walk reaches the old watermark. An interrupted walk keeps the old watermark, so nothing between is lost.
- The overlap re-reads a few alerts each run. Hash comparison makes those re-reads free.
- An unchanged organization costs one request per stream per run.

**Why a weekly reconcile on top.** The incremental walk depends on `updated_at` moving for every change we care about **(verify for all three families, especially auto-dismissal and validity changes)**, and it cannot see an alert that vanished. The reconcile pass catches both, and sweeps. If the verification shows a class of change that does not move `updated_at`, the reconcile interval for that stream drops to daily.

**Feature not enabled.** GitHub answers 403 ("Advanced Security must be enabled") or 404 for a repository or organization where a feature is off. The connector raises `FeatureNotEnabled`, the grant is recorded as `NOT_ENABLED`, and the stream is skipped for that scope without affecting health. A 403 saying "Resource not accessible by integration" is a real permission gap and raises `PermissionMissing`.

## 6. Field mappings

Mapping tables are data in `mapping.py`, and the published per-connector mapping docs are generated from them (NORM-04, NORM-10).

### Repository → Resource

| Canonical | GitHub |
|---|---|
| `type` | `REPOSITORY` |
| `name` | `full_name` |
| `url` | `html_url` |
| `state` | `ACTIVE`. `archived` or `disabled` → `INACTIVE`. Gone from the installation → `DELETED` by sweep. |
| `data.repository.repo_url` | `clone_url` |
| `data.repository` | `default_branch`, `visibility`, `fork`, `archived`, `language`, `pushed_at`, `owner.login`, `id` |
| `data.repository.security_features` | From `security_and_analysis`: `advanced_security`, `code_security`, `secret_scanning`, `secret_scanning_push_protection`, `dependabot_security_updates`, each `enabled`, `disabled` or null when GitHub does not return it |
| `tags` | `topics`, as `{key: "topic", value, source: "github"}` |
| `groups` | The owning account: `{uid: owner.id, name: owner.login}` |
| `vendor_attributes.id` | `id` |

`security_features` is the coverage record. It lets a customer answer "zero secret findings because clean, or because secret scanning is off?" without leaving our API.

### Code scanning alert → Finding

| Canonical | GitHub | Notes |
|---|---|---|
| `type` | `CODE` | |
| `title` | `rule.description`, else `rule.name`, else `rule.id` | |
| `description` | `most_recent_instance.message.text` | The rule's `full_description` and `help` are only on the single-alert endpoint and are not fetched per alert |
| `severity` | `rule.security_severity_level` | `critical`, `high`, `medium`, `low` map directly. When it is null (a non-security rule): `rule.severity` `error` → `HIGH`, `warning` → `MEDIUM`, `note` → `LOW`, `none` → `INFO`. |
| `state` | `open` → `OPEN`, `fixed` → `CLOSED`, `dismissed` → `IGNORED` | `REOPENED` is derived by the platform |
| `state_updated_at` | `fixed_at` or `dismissed_at` when set | Otherwise the platform's time |
| `has_fix`, `exploitable`, `reachability` | null | GitHub asserts none of these for code scanning. Copilot Autofix existing is not a "fix available" assertion. |
| `analytic` | `{uid: rule.id, name: rule.name, type: tool.name, url: rule.help_uri}` | |
| `product` | `{name: tool.name, vendor_name: "GitHub"}` for CodeQL. For third-party SARIF tools, `vendor_name` is null. | |
| `resource_related.affected_code` | `most_recent_instance.location`: `path`, `start_line`, `end_line`, and `html_url` | |
| `vulnerabilities[].weaknesses` | CWE ids parsed from `rule.tags` (`external/cwe/cwe-079` → `CWE-79`) | |
| `resources` | The repository (primary), and the branch from `most_recent_instance.ref` when that branch is tracked (related) | |
| `vendor_attributes` | `id` = `number`, `url` = `html_url`, `severity`, `state`, `created_at`, `updated_at` | |
| `vendor_attributes.data` | `analysis_key`, `category`, `classifications`, `commit_sha`, `ref`, `environment`, `dismissed_reason`, `dismissed_comment`, `dismissed_by.login`, `tool.version` | Matches the keys Leen exposes for GitHub |

### Secret scanning alert → Finding

| Canonical | GitHub | Notes |
|---|---|---|
| `type` | `SECRET` | |
| `title` | `secret_type_display_name` | |
| `severity` | `UNKNOWN` by default | GitHub assigns secret alerts no severity, and the platform does not invent one (NORM-09). See the option below. |
| `state` | `open` → `OPEN`. `resolved` with `revoked` → `CLOSED`. `resolved` with `false_positive`, `wont_fix`, `used_in_tests` → `IGNORED`. `resolved` with `pattern_deleted` or `pattern_edited` → `CLOSED`. | |
| `state_updated_at` | `resolved_at` when set | |
| `has_fix`, `exploitable`, `reachability` | null | |
| `analytic` | `{uid: secret_type, name: secret_type_display_name, type: "secret_scanning"}` | |
| `product` | `{name: "Secret scanning", vendor_name: "GitHub"}` | |
| `resource_related.affected_code` | `first_location_detected` (path, lines, commit URL) | With `secret_locations: all`, every location from `GET .../alerts/{n}/locations` |
| `vendor_attributes.data` | `validity`, `publicly_leaked`, `multi_repo`, `is_base64_encoded`, `has_more_locations`, `push_protection_bypassed`, `push_protection_bypassed_at`, `resolution`, `resolution_comment`, `provider` | |

**The secret itself is never stored.** Every listing request sends `hide_secret=true`, and independently the raw-capture layer and the normaliser both drop the `secret` field, so a change in GitHub's behaviour cannot leak one into our archive. A CI test asserts no fixture and no stored row contains a `secret` key.

**Severity option.** Because `UNKNOWN` makes secret findings invisible to severity filters, the connection option `secret_severity` lets a customer opt in to a derived value: a fixed level, or `by_validity` (`active` → `CRITICAL`, `unknown` → `HIGH`, `inactive` → `LOW`). When used, `severity` is listed in `_meta.derived`. This default is an open decision (part 10, section 7).

**Locations cost.** `secret_locations: all` is one extra request per alert. It is off by default and fetched only for alerts whose `has_more_locations` is true.

### Dependabot alert → Finding

| Canonical | GitHub | Notes |
|---|---|---|
| `type` | `DEPENDENCY` | |
| `title` | `security_advisory.summary` | |
| `description` | `security_advisory.description` | |
| `severity` | `security_advisory.severity` | `critical`, `high`, `medium`, `low` |
| `state` | `open` → `OPEN`, `fixed` → `CLOSED`, `dismissed` and `auto_dismissed` → `IGNORED` | |
| `state_updated_at` | `fixed_at`, `dismissed_at` or `auto_dismissed_at` | |
| `has_fix` | `true` when `security_vulnerability.first_patched_version` is present, `false` when it is null | GitHub does assert this |
| `exploitable` | null | |
| `reachability` | From the alert's reachability verdict if GitHub returns one **(verify the field exists on the plan tiers we test)**, else null | |
| `remediation` | "Upgrade `<package>` to `<first_patched_version.identifier>` or later" | Only when a patched version exists |
| `resource_related.affected_package` | `name` = `dependency.package.name`, `package_manager` = `dependency.package.ecosystem`, `version` = null | GitHub reports the vulnerable range and the manifest path, not the installed version. The range and `manifest_path` go in vendor data. |
| `vulnerabilities[]` | `uid` = `cve_id`, `cvss_scores` from `cvss_severities` (v3 and v4: score, vector), `weaknesses` from `cwes` | |
| `cve_ids` | `security_advisory.cve_id`, uppercased | A GHSA-only advisory gets its CVE from `advisory_alias` when one exists |
| `vendor_attributes.vulnerability_identifiers` | `security_advisory.identifiers` (GHSA and CVE) | |
| `vendor_attributes.data` | `dependency.manifest_path`, `dependency.scope`, `dependency.relationship`, `vulnerable_version_range`, `dismissed_reason`, `dismissed_comment`, `security_advisory.ghsa_id`, `epss`, `published_at`, `withdrawn_at` | |

Dependabot is the one family with real enrichment already in the payload (CVSS, CWE, EPSS), so vendor-supplied values fill `vulnerabilities[]` and enrichment adds only what is missing, with the vendor's values winning (ENR-05).

DEPENDENCY resources are not emitted. An alert describes a vulnerable package, not a complete inventory, and a resource list containing only vulnerable packages would mislead. The package lives in `affected_package`. A full dependency inventory is the optional `dependencies` stream in section 11.

## 7. Rate limits

- Budget key: the installation. Primary limit 5,000 requests an hour, scaling up to 12,500 with repository and user count, and 15,000 on Enterprise Cloud. The bucket's capacity is taken from the `x-ratelimit-limit` header on the first response, not hard-coded.
- Secondary limits: at most 100 concurrent requests and 900 points a minute. We run at most 4 concurrent requests and 10 a second per installation.
- A 403 or 429 with `retry-after`, or with `x-ratelimit-remaining: 0`, or whose body names a secondary limit, is `RateLimited`. The wait is the longest of the signals. Longer than 2 minutes parks the run.
- GitHub warns that continuing to send requests while limited can get an integration banned, so the budget is enforced before sending, never discovered by hitting the wall.
- Conditional requests with `ETag` are a later optimisation for the repositories stream **(verify that 304 responses are free against the primary limit)**.

Rough cost for an organization with 2,000 repositories and 50,000 alerts: a backfill is about 520 requests (500 alert pages plus 20 repository pages), and an idle hourly cycle is about 23 requests (one per alert stream plus 20 repository pages). Both fit easily within one hour's budget.

## 8. Inbound webhooks

Endpoint: `POST /v1/ingress/github/{vendor_app_id}`.

1. Read the raw body. Verify `X-Hub-Signature-256` (HMAC-SHA256, constant-time comparison) with that app's webhook secret. Reject on failure. Unsigned deliveries are never accepted.
2. Insert into `sync.ingress_delivery` keyed by `(vendor_app_id, X-GitHub-Delivery)`. A duplicate is acknowledged and dropped, which makes GitHub's redelivery safe.
3. Return 202 immediately. Processing is asynchronous, so GitHub's 10-second delivery timeout is never at risk.
4. A control task resolves `installation.id` to connections and asks the connector what the delivery means.

| Event | Actions | Effect |
|---|---|---|
| `code_scanning_alert` | created, fixed, reopened, closed_by_user, reopened_by_user, appeared_in_branch | Mark `code_scanning:<repo id>:<number>` dirty |
| `secret_scanning_alert` | created, resolved, reopened, validated, publicly_leaked | Mark dirty |
| `secret_scanning_alert_location` | created | Mark the alert dirty when `secret_locations: all` |
| `dependabot_alert` | created, fixed, dismissed, auto_dismissed, reopened, auto_reopened, reintroduced | Mark dirty |
| `dependabot_alert` | withdrawn | Mark dirty. The re-fetch returns 404 and the finding is deleted. |
| `repository` | created, deleted, archived, unarchived, renamed, transferred, publicized, privatized | Trigger the `repositories` stream |
| `security_and_analysis` | any | Mark the repository dirty, re-probe grants |
| `installation_repositories` | added, removed | Trigger `repositories`. Removal cascades to that repository's findings through the sweep. |
| `installation` | deleted | Health `UNAUTHORIZED`, owner `CUSTOMER`, schedules paused, `connection.sync.unauthorized` event. Data stays readable. |
| `installation` | suspend, unsuspend | Same as deleted, and reversed on unsuspend with a catch-up job |
| `installation` | new_permissions_accepted | Re-run the permission probe. Newly granted streams start. |
| `installation_target` | renamed | Update `connection_config.account_login` |

**Payloads are signals, never data** (PD-11). A dirty alert is re-fetched from `GET /repos/{owner}/{repo}/<family>/alerts/{number}`, so out-of-order or replayed deliveries cannot write stale state.

**Missed deliveries.** GitHub does not retry failed deliveries on its own. A maintenance task polls `GET /app/hook/deliveries?status=failure` every 15 minutes per app and redelivers through the API. Beyond that, the hourly incremental run closes any gap, which is why scheduled sync stays the source of truth.

## 9. Verify and probe

- `verify`: `GET /app/installations/{installation_id}` with the app JWT. Confirms the installation exists and is not suspended, and returns the account id for the fingerprint, the repository selection and the granted permissions.
- `probe(stream)`: first reads the installation's `permissions` map, which answers "was this permission granted" with no extra request. If granted, it makes one `per_page=1` request to the stream's endpoint to tell `GRANTED` from `NOT_ENABLED`.

A GitHub App missing the Dependabot permission therefore connects as `ACTIVE` with health `UNAUTHORIZED` and `details` naming `dependabot_alerts` and its endpoint, which is exactly AUTH-08's acceptance test.

## 10. Write-back

Requires the read-and-write app and `integration.write_back_enabled`. Exposed as one generic action, `finding.set_state` (part 7, section 7), so the action plane is not GitHub-specific.

| Request | Code scanning | Secret scanning | Dependabot |
|---|---|---|---|
| Ignore, reason `false_positive` | `dismissed`, "false positive" | `resolved`, `false_positive` | `dismissed`, `inaccurate` |
| Ignore, reason `accepted_risk` | `dismissed`, "won't fix" | `resolved`, `wont_fix` | `dismissed`, `tolerable_risk` |
| Ignore, reason `test_code` | `dismissed`, "used in tests" | `resolved`, `used_in_tests` | `dismissed`, `not_used` |
| Close, reason `revoked` | not applicable | `resolved`, `revoked` | not applicable |
| Reopen | `open` | `open` | `open` |

- `fixed` cannot be written for any family. GitHub sets it when a scan no longer finds the problem.
- A comment is passed through, truncated to GitHub's 280 characters with the truncation reported.
- After a successful `PATCH`, the alert is marked dirty and re-fetched, so our state reflects what GitHub recorded, not what we asked for (ACT-02's round-trip test).
- Writes cost 5 rate points each and draw from the interactive share of the budget.

## 11. Enterprise Server, GHE.com, and optional streams

**GHES and GHE.com.** The customer registers an app on their instance and creates a customer-owned `vendor_app` with its base URL, app id, private key and webhook secret. The dashboard walks through it, and the app manifest flow (which pre-fills permissions and events from a URL) is used where the instance supports it. API base URLs are `https://<host>/api/v3` for GHES and `https://api.<subdomain>.ghe.com` for GHE.com.

- The base URL passes the egress policy at creation and on every request.
- At verify, `GET /meta` gives the server version. The manifest declares a minimum version per stream, and a stream below it is granted `UNSUPPORTED`. **(verify the minimum GHES version for each organization-level alert endpoint against the versioned docs)**
- GHES rate limits are set by the instance's admin and may be off. The bucket adapts from response headers and falls back to a conservative default.
- Webhooks need the instance to reach our API. Where it cannot, the connection runs on schedules alone, and that is a supported configuration.
- A GHES instance on a private network needs the relay agent (AUTH-13), which is out of scope.

**Optional streams, designed for and not built in this plan.**

| Stream | Why it waits |
|---|---|
| `dependencies` (SBOM, DEPENDENCY resources) | Not part of Advanced Security. GitHub's SBOM API is moving to an asynchronous report flow **(verify)**, which fits the export primitive when a customer asks. |
| `code_scanning_analyses` | Coverage detail (which tools ran, when). Useful later for posture. |
| `repository_advisories` | A different object (advisories a repository publishes), not a finding against it. |
| Enterprise-level listings | Only Dependabot has a confirmed enterprise endpoint. Organization installations cover the need. |

## 12. Test tenant

`tools/github-seed` creates and maintains an organization that produces every case the connector must handle:

- Public repositories with known-vulnerable dependencies in npm, pip, Maven and Go manifests, for Dependabot.
- Public repositories with code CodeQL flags in several languages, plus one uploading third-party SARIF, for code scanning.
- Public repositories containing revoked and vendor-published test secrets, for secret scanning.
- Alerts in every state: open, fixed, dismissed with each reason, auto-dismissed, reopened.
- An archived repository, a renamed repository, a fork, an empty repository, and one with each feature disabled.
- A second installation on a user account, for per-repository mode.
- A second installation with selected repositories only.

Public repositories make all three features free. Private-repository behaviour (the 403 and 404 paths without add-ons) is tested with one private repository and no add-ons, which costs nothing, and the paid path is tested for one month before launch (about 53 USD per committer).

The nightly live sync (CDK-07) runs against this organization, and a scheduled seed task keeps it changing: it opens and dismisses an alert each night so incremental sync always has something to find.
