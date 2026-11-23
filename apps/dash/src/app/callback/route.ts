import { type NextRequest, NextResponse } from "next/server";
import {
	COOKIE_OPTIONS,
	exchangeCode,
	SESSION_COOKIE,
	STATE_COOKIE,
	seal,
} from "@/lib/session";

const MAX_COOKIE_BYTES = 3800;

/** WorkOS redirects here with `code` and our `state` after hosted sign-in. */
export async function GET(request: NextRequest) {
	const params = request.nextUrl.searchParams;
	const code = params.get("code");
	const raw = request.cookies.get(STATE_COOKIE)?.value;
	let expected: { returnTo: string; state: string } | null = null;
	try {
		expected = raw
			? (JSON.parse(raw) as { returnTo: string; state: string })
			: null;
	} catch {
		expected = null;
	}
	if (!(code && expected) || params.get("state") !== expected.state) {
		return NextResponse.redirect(new URL("/login?error=state", request.url));
	}
	try {
		const session = await exchangeCode(code);
		const returnTo = expected.returnTo.startsWith("/")
			? expected.returnTo
			: "/";
		const sealed = await seal(session);
		if (sealed.length > MAX_COOKIE_BYTES) {
			// Browsers silently drop cookies over ~4 KB. Setting it anyway would send
			// you back to sign-in, which signs you straight in again: a loop.
			return new NextResponse(
				`Sign-in failed: the session cookie would be ${sealed.length} bytes, over the ${MAX_COOKIE_BYTES}-byte browser limit. Trim the claims WorkOS puts in the access token (roles, permissions, custom claims).`,
				{ status: 500 }
			);
		}
		const response = NextResponse.redirect(new URL(returnTo, request.url));
		response.cookies.set(SESSION_COOKIE, sealed, COOKIE_OPTIONS);
		response.cookies.delete(STATE_COOKIE);
		return response;
	} catch (error) {
		const message = error instanceof Error ? error.message : "sign-in failed";
		return new NextResponse(`Sign-in failed: ${message}`, { status: 502 });
	}
}
