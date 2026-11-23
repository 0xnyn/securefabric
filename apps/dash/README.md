# dash

The SecureFabric dashboard (Next.js 16, React 19). Everything it shows comes from the API.

```bash
make dev-dash    # this app + the client watcher (API expected on :8000; `make dev` runs everything)
make test-dash   # vitest
```

- **Data**: `src/lib/store.ts` holds the workspace snapshot from `GET /api/v1/workspace` (`useWorkspace()`), polls every second while a sync runs and every 10s otherwise, and exposes the actions (`createConnection`, `triggerSync`, `rollApiKey`…) as typed API calls. Simple edits apply optimistically; failures are toasted and rolled back by the refetch. If the API is down, the shell says so and points at `make dev` / `make status`.
- **Types**: `src/lib/types.ts` aliases the generated API schemas (`@securefabric/client`), so a backend model change breaks `pnpm typecheck` here until the UI catches up. Run `make generate` after changing Python models.
- **Status**: `/[env]/status` renders `GET /api/v1/status` (database, migrations, workers, queues, workspace).
- **Catalog**: `src/lib/catalog.ts` is the provider catalog's source of truth. `pnpm export-catalog` (part of `make generate`) writes the backend's copy; `pnpm check-catalog` fails when it's stale.
- **API URL**: `NEXT_PUBLIC_API_URL` in `apps/dash/.env.local` (default `http://localhost:8000`). The API must allow the origin: `API_CORS_ORIGINS` in the root `.env`.
- **Still simulated in the browser**: sandbox records, metrics, and the playground's unified-API responses (`src/lib/endpoints.ts`, `records.ts`).
