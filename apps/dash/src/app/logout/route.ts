import { type NextRequest, NextResponse } from "next/server";
import { logoutUrl, SESSION_COOKIE, type Session, unseal } from "@/lib/session";

export async function GET(request: NextRequest) {
	const session = await unseal<Session>(
		request.cookies.get(SESSION_COOKIE)?.value
	);
	const target = logoutUrl(session, new URL("/login", request.url).toString());
	const response = NextResponse.redirect(target);
	response.cookies.delete(SESSION_COOKIE);
	return response;
}
