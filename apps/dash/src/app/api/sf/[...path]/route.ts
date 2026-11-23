import { type NextRequest, NextResponse } from "next/server";
import {
	COOKIE_OPTIONS,
	devApiKey,
	freshSession,
	SESSION_COOKIE,
	type Session,
	seal,
	unseal,
} from "@/lib/session";

/**
 * The dashboard's same-origin route to the SecureFabric API (backend for
 * frontend). The dashboard uses the public API, nothing private (part 8,
 * section 2); this route only attaches credentials, so tokens never reach
 * browser JavaScript.
 */
const API_URL =
	process.env.SF_API_URL ??
	process.env.NEXT_PUBLIC_API_URL ??
	"http://localhost:8000";

const FORWARD_REQUEST = [
	"accept",
	"content-type",
	"idempotency-key",
	"prefer",
	"x-connection-id",
	"x-environment-id",
	"x-organization-id",
	"x-request-id",
	// Operator access and repairs state why (OPS-01); the API audits it.
	"x-support-reason",
];
const FORWARD_RESPONSE = [
	"content-type",
	"idempotent-replayed",
	"retry-after",
	"x-ratelimit-limit",
	"x-ratelimit-remaining",
	"x-ratelimit-reset",
	"x-request-id",
	"x-unsupported-filters",
];

function problem(status: number, code: string, detail: string): NextResponse {
	return NextResponse.json(
		{
			code,
			detail,
			errors: [],
			request_id: null,
			status,
			title: "Authentication required",
			type: "about:blank",
		},
		{ headers: { "content-type": "application/problem+json" }, status }
	);
}

const TRAILING_SLASH = /\/$/u;
const UPSTREAM_TIMEOUT_MS = 60_000;

/** Send the request to the API; a problem response if it is down or hung. */
async function forward(
	request: NextRequest,
	target: string,
	headers: Headers
): Promise<Response | NextResponse> {
	const body = ["GET", "HEAD"].includes(request.method)
		? undefined
		: await request.arrayBuffer();
	try {
		return await fetch(target, {
			body,
			cache: "no-store",
			headers,
			method: request.method,
			redirect: "manual",
			// An API that accepts the connection but never answers (a dev server
			// whose reload failed to import) must surface as an error, not as a
			// dashboard that loads forever.
			signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
		});
	} catch (error) {
		const timedOut =
			error instanceof DOMException && error.name === "TimeoutError";
		return NextResponse.json(
			{
				code: timedOut ? "api_timeout" : "api_unreachable",
				detail: timedOut
					? `${API_URL} did not answer within ${UPSTREAM_TIMEOUT_MS / 1000} s`
					: `Can't reach ${API_URL}`,
				errors: [],
				status: timedOut ? 504 : 502,
				title: timedOut ? "Gateway timeout" : "Bad gateway",
				type: "about:blank",
			},
			{ status: timedOut ? 504 : 502 }
		);
	}
}

async function handle(
	request: NextRequest,
	ctx: { params: Promise<{ path: string[] }> }
) {
	const { path } = await ctx.params;
	const target = `${API_URL.replace(TRAILING_SLASH, "")}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
	const headers = new Headers();
	for (const name of FORWARD_REQUEST) {
		const value = request.headers.get(name);
		if (value) {
			headers.set(name, value);
		}
	}
	let refreshed: Session | null = null;
	const dev = devApiKey();
	if (dev) {
		headers.set("authorization", `Bearer ${dev}`);
	} else {
		const session = await unseal<Session>(
			request.cookies.get(SESSION_COOKIE)?.value
		);
		if (!session) {
			return problem(401, "unauthenticated", "Sign in to use the dashboard.");
		}
		try {
			const [fresh, changed] = await freshSession(session);
			if (changed) {
				refreshed = fresh;
			}
			headers.set("authorization", `Bearer ${fresh.access_token}`);
		} catch {
			const res = problem(
				401,
				"session_expired",
				"Your session expired. Sign in again."
			);
			res.cookies.delete(SESSION_COOKIE);
			return res;
		}
	}
	const upstream = await forward(request, target, headers);
	if (upstream instanceof NextResponse) {
		return upstream;
	}
	const out = new Headers();
	for (const name of FORWARD_RESPONSE) {
		const value = upstream.headers.get(name);
		if (value) {
			out.set(name, value);
		}
	}
	const response = new NextResponse(
		upstream.status === 204 ? null : await upstream.arrayBuffer(),
		{
			headers: out,
			status: upstream.status,
		}
	);
	if (refreshed) {
		response.cookies.set(SESSION_COOKIE, await seal(refreshed), COOKIE_OPTIONS);
	}
	return response;
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
