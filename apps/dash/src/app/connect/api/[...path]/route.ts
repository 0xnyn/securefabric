import { type NextRequest, NextResponse } from "next/server";
import { CONNECT_COOKIE } from "@/lib/connect-cookie";

/**
 * The connect page's route to the API. It forwards only the three connect
 * endpoints, with the session token from the `/connect`-scoped cookie as the
 * bearer. Nothing else is reachable with a connect cookie.
 */
const API_URL = (
	process.env.SF_API_URL ??
	process.env.NEXT_PUBLIC_API_URL ??
	"http://localhost:8000"
).replace(/\/$/u, "");

const ALLOWED = [
	/^v1\/connect\/session$/u,
	/^v1\/connect\/connections$/u,
	/^v1\/connect\/connections\/[0-9a-f-]{36}$/u,
];

function problem(status: number, code: string, detail: string): NextResponse {
	return NextResponse.json(
		{
			code,
			detail,
			errors: [],
			request_id: null,
			status,
			title: detail,
			type: "about:blank",
		},
		{ headers: { "content-type": "application/problem+json" }, status }
	);
}

async function handle(
	request: NextRequest,
	ctx: { params: Promise<{ path: string[] }> }
) {
	const path = (await ctx.params).path.join("/");
	if (!ALLOWED.some((re) => re.test(path))) {
		return problem(404, "not_found", "Not found");
	}
	const token = request.cookies.get(CONNECT_COOKIE)?.value;
	if (!token) {
		return problem(
			401,
			"connect_session_missing",
			"This connect link is missing or was opened in another browser."
		);
	}
	const headers = new Headers({ authorization: `Bearer ${token}` });
	for (const name of ["content-type", "idempotency-key", "x-request-id"]) {
		const value = request.headers.get(name);
		if (value) {
			headers.set(name, value);
		}
	}
	try {
		const upstream = await fetch(`${API_URL}/${path}`, {
			body: request.method === "GET" ? undefined : await request.arrayBuffer(),
			cache: "no-store",
			headers,
			method: request.method,
		});
		const out = new Headers({ "cache-control": "no-store" });
		for (const name of ["content-type", "x-request-id", "retry-after"]) {
			const value = upstream.headers.get(name);
			if (value) {
				out.set(name, value);
			}
		}
		return new NextResponse(await upstream.arrayBuffer(), {
			headers: out,
			status: upstream.status,
		});
	} catch {
		return problem(
			502,
			"api_unreachable",
			"SecureFabric is unreachable. Try again in a moment."
		);
	}
}

export const GET = handle;
export const POST = handle;
