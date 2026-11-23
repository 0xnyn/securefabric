import { ClientResponseError } from "@securefabric/client";

/**
 * Codes the `/api/sf` route (or the API) answers when the dashboard session is
 * missing or can no longer be refreshed: signing in again fixes them. Other
 * 401s (`invalid_session`, `sessions_disabled`, ...) mean the API rejects a
 * valid sign-in, usually a WorkOS mismatch between apps/dash/.env.local and
 * the root .env; signing in again would only loop, so those are shown instead.
 */
const SIGN_IN_AGAIN = new Set(["unauthenticated", "session_expired"]);

/** Don't send the same tab to sign-in twice within this window. */
const LOOP_GUARD_MS = 20_000;
const LOOP_GUARD_KEY = "sf_sign_in_redirect_at";

export function needsSignIn(error: unknown): boolean {
	return (
		error instanceof ClientResponseError &&
		error.status === 401 &&
		SIGN_IN_AGAIN.has(error.code)
	);
}

/**
 * Send the browser to sign-in (and back here afterwards) when `error` says the
 * session is gone. Returns false, and does nothing, when the error is something
 * else or when this tab was already sent to sign-in moments ago: that means
 * signing in did not help, and the shell shows the error instead of looping.
 */
export function redirectToSignIn(error: unknown): boolean {
	if (!needsSignIn(error) || typeof window === "undefined") {
		return false;
	}
	try {
		const last = Number(window.sessionStorage.getItem(LOOP_GUARD_KEY) ?? 0);
		if (Date.now() - last < LOOP_GUARD_MS) {
			return false;
		}
		window.sessionStorage.setItem(LOOP_GUARD_KEY, String(Date.now()));
	} catch {
		// No sessionStorage (privacy mode): redirect without the guard.
	}
	const returnTo = window.location.pathname + window.location.search;
	window.location.assign(`/login?return_to=${encodeURIComponent(returnTo)}`);
	return true;
}

/** Retry transient failures, never auth failures (they won't fix themselves). */
export function retryUnlessAuth(failureCount: number, error: unknown): boolean {
	if (error instanceof ClientResponseError && error.status === 401) {
		return false;
	}
	return failureCount < 3;
}
