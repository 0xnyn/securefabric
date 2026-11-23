# docs

SecureFabric's customer documentation, built with [Mintlify](https://mintlify.com) (`docs.json`).

```sh
pnpm -F docs dev               # preview at http://localhost:3333 (or: pnpm dev:docs from the root)
pnpm -F docs generate          # rewrite api-reference/openapi.json from the API
pnpm -F docs check-generated   # fail if api-reference/openapi.json is stale
pnpm -F docs lint              # mint broken-links
pnpm -F docs check             # mint validate: content, OpenAPI, strict build
```

`pnpm dev` and `make dev` at the root don't start the docs (`--filter=!docs`), so the preview never competes with the dash for a port.

## Layout

| Path | What it is |
|---|---|
| `docs.json` | Site config: theme, colors, navigation (tabs: Guides, Connectors, API reference, Changelog), playground, redirects. |
| `index.mdx`, `quickstart.mdx`, `glossary.mdx` | Get started. |
| `concepts/`, `guides/`, `connect/`, `webhooks/`, `dashboard/` | Guides tab. |
| `connectors/` | One page per connector. `overview.mdx` and the coming-soon pages were generated from the roadmap research (tiers A/B/C and connector cards); edit them by hand from here on. |
| `api-reference/*.mdx` | Hand-written API overview pages (authentication, errors, pagination, ...) and the typed client guides. |
| `api-reference/openapi.json` | **Generated. Don't edit.** Endpoint pages are built from it, grouped by tag. |
| `scripts/openapi.mjs` | Turns `securefabric-openapi` output into `openapi.json`. |
| `logo/`, `favicon.svg` | Brand mark and wordmark; `logo/connectors/` holds vendor logos copied from `apps/dash/public/integrations/`. |

## The API reference

The endpoint pages are never written by hand. `generate` runs

```sh
uv run --frozen securefabric-openapi | node apps/docs/scripts/openapi.mjs apps/docs/api-reference/openapi.json
```

and the script only adds presentation on top of the API's schema: `servers`, the bearer `securitySchemes`, each operation's required scope, `Idempotency-Key` on the operations that honour it, `application/problem+json` error bodies, tag display names, sentence-case titles, and `x-excluded` on operator-only and dashboard-session-only operations. Keys are sorted (except paths, methods and schema properties, whose order is the sidebar and field order), so a regenerated file diffs cleanly.

When you add or rename an API route:

1. Run `pnpm -F docs generate` (next to `make generate` for the TypeScript client) and commit `api-reference/openapi.json`.
2. If the script warns `no scope listed for <operation>`, add the operation to `SCOPES` (or `ANY_KEY`, `PUBLIC`, ...) in `scripts/openapi.mjs`. If it fails with `names unknown operations`, a listed operation was renamed or removed: update the list.
3. If the route takes `IdempotencyDep`, add it to `IDEMPOTENT`.

`check-generated` runs with the other packages' (`pnpm check-generated`, `make verify`). The package depends on `api` (`workspace:*`) so Turborepo reruns it when the API changes.

## Writing

- Sentence case for every heading, nav label and button; second person; present tense; verb-first how-to titles ("Verify webhook signatures").
- Use the terms in `glossary.mdx` with exactly those meanings: environment, organization, integration, connection, finding, resource.
- Every endpoint, parameter, scope, error code, header, event type and health code must exist in the code. Grep before you write it.
- Error tables follow what happened, then how to fix it.
- No internal detail: no database, queue, worker or vault internals.
