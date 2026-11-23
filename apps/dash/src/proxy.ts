import { type NextRequest, NextResponse } from "next/server";
import {
	devApiKey,
	SESSION_COOKIE,
	type Session,
	unseal,
	workosConfigured,
} from "@/lib/session";

/**
 * Optimistic auth check: every dashboard page needs a session cookie, except the
 * hosted connect flow (authenticated by its own session token), the sign-in
 * routes and the API proxy (which answers 401 itself). The API verifies the
 * WorkOS token on every request; this only saves a round trip.
 *
 * The cookie must also decrypt: one sealed with an older
 * WORKOS_COOKIE_PASSWORD (or left by an older build) would otherwise let the
 * page load and then fail every API call with nothing to send you to sign-in.
 */
export async function proxy(request: NextRequest) {
	if (devApiKey() || !workosConfigured()) {
		return NextResponse.next();
	}
	const session = await unseal<Session>(
		request.cookies.get(SESSION_COOKIE)?.value
	);
	if (session?.refresh_token) {
		return NextResponse.next();
	}
	const login = new URL("/login", request.url);
	login.searchParams.set(
		"return_to",
		request.nextUrl.pathname + request.nextUrl.search
	);
	const response = NextResponse.redirect(login);
	if (request.cookies.has(SESSION_COOKIE)) {
		response.cookies.delete(SESSION_COOKIE);
	}
	return response;
}

export const config = {
	matcher: [
		"/((?!_next/|api/|connect/|connect$|callback|login|logout|favicon\\.ico|icon\\.svg|apple-icon|opengraph-image|integrations/).*)",
	],
};
