import { type NextRequest, NextResponse } from "next/server";
import { connectCookie, TOKEN_PATTERN } from "@/lib/connect-cookie";

/**
 * `GET /connect/{token}`: the link a customer receives. Swap the token for a
 * cookie and continue on `/connect` without it in the address bar. `origin`
 * (set by connect-js) is kept so the page knows where to post its result.
 */
export function GET(
	request: NextRequest,
	ctx: { params: Promise<{ token: string }> }
) {
	return ctx.params.then(({ token }) => {
		const next = new URL("/connect", request.url);
		const origin = request.nextUrl.searchParams.get("origin");
		if (origin) {
			next.searchParams.set("origin", origin);
		}
		if (!TOKEN_PATTERN.test(token)) {
			next.searchParams.set("error", "invalid_link");
			return NextResponse.redirect(next);
		}
		const response = NextResponse.redirect(next, 303);
		const secure =
			request.nextUrl.protocol === "https:" ||
			request.headers.get("x-forwarded-proto") === "https";
		response.headers.append("set-cookie", connectCookie(token, secure));
		response.headers.set("cache-control", "no-store");
		response.headers.set("referrer-policy", "no-referrer");
		return response;
	});
}
