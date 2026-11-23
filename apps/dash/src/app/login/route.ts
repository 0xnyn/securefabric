import { type NextRequest, NextResponse } from "next/server";
import {
	authorizeUrl,
	devApiKey,
	STATE_COOKIE,
	workosConfigured,
} from "@/lib/session";

/** Start WorkOS AuthKit sign-in. In dev-key mode there is nothing to sign in to. */
export function GET(request: NextRequest) {
	const returnTo = request.nextUrl.searchParams.get("return_to") ?? "/";
	if (devApiKey() || !workosConfigured()) {
		return NextResponse.redirect(new URL(returnTo, request.url));
	}
	const state = crypto.randomUUID();
	const redirectUri =
		process.env.NEXT_PUBLIC_WORKOS_REDIRECT_URI ??
		new URL("/callback", request.url).toString();
	const response = NextResponse.redirect(
		authorizeUrl(
			redirectUri,
			state,
			request.nextUrl.searchParams.get("screen_hint") ?? undefined
		)
	);
	response.cookies.set(STATE_COOKIE, JSON.stringify({ returnTo, state }), {
		httpOnly: true,
		maxAge: 600,
		path: "/",
		sameSite: "lax",
		secure: process.env.NODE_ENV === "production",
	});
	return response;
}
