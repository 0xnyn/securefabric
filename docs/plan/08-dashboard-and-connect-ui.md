# Part 8: Dashboard and connect UI

## 1. Where the dashboard is today

`apps/dash` is a well-built shell on a mock. The shell, the data-table kit, the command palette, the design tokens and the environment switcher are real and stay. The data is not: every view except Workflows reads a seeded store in localStorage, and the Python `domain` package mirrors that store without any route exposing it.

The mock was modelled on Nango's dashboard, and three of its concepts do not match the platform this plan builds:

| Mock concept | Platform concept | Change |
|---|---|---|
| A connection has a `customer {email, endUserId, orgName}` | A connection belongs to an Organization | Organizations become a first-class list and the parent of connections |
| 15 model keys (devices, detections, tickets, ...) | Two objects: resources and vulnerability findings | The model list shrinks to what exists. Reserved objects appear only when a connector emits them. |
| Playground with simulated endpoints (isolate device, create ticket, suspend user) | The real API | Replaced by a request console against real endpoints |

## 2. Principles

1. **The dashboard uses the public API.** No private backend for the UI. If the dashboard needs something, it becomes an endpoint customers can also call. The few session-only endpoints (members, environments) are the exception.
2. **Types come from the API.** The existing chain (Pydantic → OpenAPI → `packages/client` → TanStack Query hooks) is the only way data enters a view. `check-generated` already fails CI on drift.
3. **One view at a time.** Each view moves from the mock store to real hooks in its own change. The mock store is deleted when the last view leaves it. There is no mode switch between mock and real, which would double the surface to maintain.
4. **Server state lives in TanStack Query, URL state in `nuqs`.** Filters, sort and cursor are in the URL, so every table state is shareable. This is already the data-table kit's design.

## 3. Views

| Route | Status | What it becomes | API |
|---|---|---|---|
| `/[env]` Overview | Rewire | Connection count by health, freshness breaches, jobs in the last 24 hours, findings by severity, recent health changes | `/connections`, `/usage`, `/operations` |
| `/[env]/catalog`, `/catalog/[provider]` | Rewire | The connector catalogue from manifests: auth mode, streams, permissions guide, capabilities, field coverage | `/connectors` |
| `/[env]/integrations`, `/integrations/[id]` | Rewire | Enabled connectors: streams, default intervals, vendor app (shared or own), write-back toggle | `/integrations`, `/vendor_apps` |
| `/[env]/organizations`, `/organizations/[id]` | New | End customers and their connections | `/organizations` |
| `/[env]/connections` | Rewire | Table with health, freshness, counts, filters by organization, vendor, health code, tags | `/connections` |
| `/[env]/connections/[id]` | Rewire | Tabs: Overview (health object, per-stream status, freshness, grants and coverage), Jobs, Findings, Resources, Authorization (what is set and when, never values), Settings (options, intervals, pause, reset, delete) | `/connections/{id}`, `/jobs`, data endpoints |
| `/[env]/jobs/[id]` | New | Per-stream results, counts, health code, timeline, logs | `/jobs/{id}`, `/jobs/{id}/logs` |
| `/[env]/findings`, `/[env]/resources` | New | The data explorer (OBS-02): server-side filters, sort and keyset paging, a detail sheet with the canonical record, vendor attributes and state history | Data endpoints |
| `/[env]/logs` | Rewire | Operation log with the existing filter rail | `/operations` |
| `/[env]/webhooks` (moves out of Settings) | Rewire | Endpoints, event subscriptions, secret rotation, delivery log, replay | `/webhook_endpoints` |
| `/[env]/keys` | Rewire | Create with scopes, show once, revoke | `/api_keys` |
| `/[env]/metrics` | Rewire | API requests, sync volume, error rates, from usage rollups | `/usage` |
| `/[env]/playground` | Replace | A request console: pick an endpoint from the OpenAPI document, pick a connection, send, see the response and the equivalent curl | Any |
| `/[env]/settings` | Rewire | General, connect UI branding, team (WorkOS invitations and roles) | `/environments`, `/members` |
| `/[env]/workflows` | Remove | Superseded by Jobs | |
| `/connect/[token]` | New | The hosted connect flow, section 5 | `/connect/*` |

**The data-table contract.** `lib/data-table/contract.ts` already defines a wire contract for list endpoints with `cursor`, `size`, `sort` and filter encodings. It was written for the mock's offset-style paging. It is adapted, once, to the API's real shape (`limit`, `cursor`, `next_cursor`, `previous_cursor`, `sort=field:dir`), and the kit's transport is the only place that knows the mapping. Facet counts come from a small `summary` query per view where they are cheap, and are omitted where they are not.

## 4. Auth in the dashboard

- WorkOS AuthKit through its Next.js integration: middleware protects every route except `/connect/*`, and the session provides an access token.
- `lib/api.ts` attaches the token and `X-Environment-Id` (resolved from the `[env]` slug against `/v1/environments`).
- The first sign-in lands on an onboarding step that names the account. Environments `dev` and `prod` already exist.
- The role is read from `/v1/me`. In this plan it gates only destructive actions and the team page.

## 5. The connect UI

The connect flow is specified in part 3, section 8. Its UI is a route in `apps/dash` so it shares the component kit and build:

- `/connect/[token]`: no dashboard chrome, no WorkOS session. Authenticated only by the session token in the URL, which the page exchanges for a short-lived cookie scoped to `/connect` so the token leaves the address bar.
- Screens: pick an integration (skipped if the session allows one), the permission guide, then either a schema-rendered form or a "Continue to GitHub" button, a waiting state while verification runs, and a result. Error states name the cause: session expired, session already used, vendor denied, permission missing with the list of missing permissions.
- The form renderer takes the connector's JSON Schema (titles, descriptions, patterns, secret flags, order, conditional visibility) and nothing else (CAT-04). SANDBOX exercises it, since GitHub has no form.
- Branding from `environment.settings`: name, logo, accent colour, light or dark.

**Embedding.** `packages/connect-js` is a small script with no framework dependency plus a thin React wrapper:

```ts
const connect = SecureFabric.connect({ token, onSuccess, onError, onClose });
connect.open();
```

It opens the hosted page in an iframe modal and relays events by `postMessage` with strict origin checks. The page sets `frame-ancestors` to the environment's allowed origins. For GitHub the redirect to github.com cannot happen inside an iframe, so the embed opens a popup for that step and the iframe waits for it, which is how GitHub App installs behave in every embedded product.

## 6. Internal admin console

OPS-01 asks that support resolve a stuck connection without database access. This is not a separate app. It is the same dashboard with an operator role that can open any account, read-only, with a reason, and every such session is recorded in the audit log (OPS-05). On top of what a customer sees, an operator gets:

- Search by connection id, organization, account or vendor tenant across accounts.
- The scheduler view: queued, admitted, parked and retrying runs, with why each is waiting.
- Raw page viewer for a job, behind a reason prompt, audited (RAW-02).
- Controls: trigger, pause, reset, re-normalise, purge, rebuild counts (OPS-08).
- The runbook for the connection's current health code.

Operator access is granted by a flag on `app_user` that only a migration or a break-glass command can set.

## 7. Documentation site

A docs site (DX-01) is generated from three sources so it cannot drift: the OpenAPI document (reference), connector manifests and `docs.md` files (per-connector pages with permissions, mappings, capabilities and field coverage), and hand-written guides (quickstart, authentication, pagination and incremental sync, webhook verification in curl, Python, TypeScript and Go, the Leen migration guide). Where it is hosted and which generator is used are left to the delivery milestone.
