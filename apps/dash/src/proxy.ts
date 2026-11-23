import { type NextRequest, NextResponse } from "next/server";

/**
 * Optimistic auth check: every dashboard page needs a session cookie, except the
 * hosted connect flow (authenticated by its own session token), the sign-in
 * routes and the API proxy (which answers 401 itself). The API verifies the
 * WorkOS token on every request; this only saves a round trip.
 */
export function proxy(request: NextRequest) {
	if (process.env.SF_DEV_API_KEY || process.env.NEXT_PUBLIC_SF_DEV_API_KEY) {
		return NextResponse.next();
	}
	if (
		!(
			process.env.WORKOS_CLIENT_ID &&
			process.env.WORKOS_API_KEY &&
			process.env.WORKOS_COOKIE_PASSWORD
		)
	) {
		return NextResponse.next();
	}
	if (request.cookies.has("sf_session")) {
		return NextResponse.next();
	}
	const login = new URL("/login", request.url);
	login.searchParams.set(
		"return_to",
		request.nextUrl.pathname + request.nextUrl.search
	);
	return NextResponse.redirect(login);
}

export const config = {
	matcher: [
		"/((?!_next/|api/|connect/|connect$|callback|login|logout|favicon\\.ico|icon\\.svg|apple-icon|opengraph-image|integrations/).*)",
	],
};
