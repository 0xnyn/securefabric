import { createClient } from "@securefabric/client";

/**
 * Where the SecureFabric API lives. `make dev` runs it on :8000; point the
 * dash elsewhere with NEXT_PUBLIC_API_URL (inlined at build time).
 */
export const API_URL =
	process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * The one typed client for the browser. Every call is checked against the
 * FastAPI schema through `@securefabric/client` (regenerate with
 * `make generate`), so a renamed field or route breaks `pnpm typecheck`,
 * not production.
 */
export const api = createClient(API_URL);
