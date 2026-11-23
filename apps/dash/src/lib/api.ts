import { createClient } from "@securefabric/client";

/**
 * Where the SecureFabric API lives, for display (docs, curl samples). The
 * browser never calls it directly: it calls the same-origin `/api/sf` route,
 * which attaches the session (or the dev API key) server-side.
 */
export const API_URL =
	process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** The proxy prefix every dashboard request goes through. */
export const PROXY_BASE = "/api/sf";

/** An absolute base for openapi-fetch (it builds `Request` objects). */
function base(): string {
	if (typeof window !== "undefined") {
		return `${window.location.origin}${PROXY_BASE}`;
	}
	return `http://localhost${PROXY_BASE}`;
}

/** A client with no environment: `/v1/me`, `/v1/environments`, the catalogue. */
export const api = createClient(base());

const scoped = new Map<string, ReturnType<typeof createClient>>();

/** A client that sends `X-Environment-Id` (session principals pick one per request). */
export function envClient(
	environmentId: string
): ReturnType<typeof createClient> {
	let c = scoped.get(environmentId);
	if (!c) {
		c = createClient(base(), {
			headers: { "X-Environment-Id": environmentId },
		});
		scoped.set(environmentId, c);
	}
	return c;
}

export type ApiClient = ReturnType<typeof createClient>;
