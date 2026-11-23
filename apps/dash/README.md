# dash

The SecureFabric dashboard (Next.js 16, React 19). Everything it shows comes from the API.

```bash
make dev-dash    # this app + the client watcher (API expected on :8000; `make dev` runs everything)
make test-dash   # vitest
```

- **Components**: controls and layout pieces come from the design system in `packages/ui` (`@securefabric/ui/components/*`, `/patterns/*`, `/primitives/*`; see its README). This app keeps only what knows SecureFabric: `src/components/domain` (connector logos, badges, query states, role gating, the schema form), `shell` (the frame), `data-table` (the log viewer), `connect` (the hosted connect page) and `views` (one per page). Browse all of it with `pnpm storybook`.
- **Data**: `src/lib/store.ts` holds the workspace snapshot from `GET /api/v1/workspace` (`useWorkspace()`), polls every second while a sync runs and every 10s otherwise, and exposes the actions (`createConnection`, `triggerSync`, `rollApiKey`…) as typed API calls. Simple edits apply optimistically; failures are toasted and rolled back by the refetch. If the API is down, the shell says so and points at `make dev` / `make status`.
- **Types**: `src/lib/types.ts` aliases the generated API schemas (`@securefabric/client`), so a backend model change breaks `pnpm typecheck` here until the UI catches up. Run `make generate` after changing Python models.
- **Roles**: `src/lib/access.ts` mirrors the API's roles (admin, developer, support) and scopes. Nav items carry a `requires` (`src/lib/nav.ts`): the sidebar, ⌘K palette and G-shortcuts hide what a role can't use, the shell shows a "no access" page for a typed URL, and `<Gated>` (`src/components/domain/access.tsx`) disables write controls with a tooltip saying why. The API stays the authority; this only keeps the UI from offering a 403.
- **Status**: `/[env]/status` is written for customers: a plain-language headline, the services they depend on, response times measured from the browser, and this environment's sync health. Raw worker, queue and run facts sit under "Technical details" for admins and operators. Source: `GET /v1/status`, `/v1/connections`, `/v1/usage`.
- **Catalog**: live connectors come from `GET /v1/connectors` (their manifests). `src/lib/connector-catalog.ts` adds logos that work in both themes (marks that are dark on transparent ship a `-dark` twin in `public/integrations/`) and the roadmap connectors, shown greyed out as "Coming soon" until the API lists them.
- **Logs and audit log**: both use the shared log viewer (`src/components/data-table/data-table-infinite.tsx`): a filter rail, a filter command, scroll-to-load keyset pages and a details sheet with ↑/↓. Filters live in the URL. The audit log's filters, counts and histogram are computed by the API (`GET /v1/audit_events`, `/v1/audit_events/facets`), so it costs the same at any size.
- **Connect page branding**: Settings → Connect page previews the real hosted connect page in a frame (`/connect/preview`, driven by `postMessage`), in light and dark. Without branding, the connect page shows the SecureFabric mark and name.
- **Docs**: the in-app request console is gone; the API reference and guides live in the Mintlify site in `apps/docs`. `DOCS_URL` in `src/lib/nav.ts` points at it.
- **API URL**: `NEXT_PUBLIC_API_URL` in `apps/dash/.env.local` (default `http://localhost:8000`). The API must allow the origin: `API_CORS_ORIGINS` in the root `.env`.
- **Still simulated in the browser**: sandbox records, metrics, and the playground's unified-API responses (`src/lib/endpoints.ts`, `records.ts`).
