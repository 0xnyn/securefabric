/**
 * Dashboard sessions (docs/plan/03-tenancy-connections-vault.md, section 2).
 *
 * WorkOS AuthKit hosted login → `/callback` exchanges the code server-side →
 * the access and refresh tokens live in an AES-GCM sealed, httpOnly cookie.
 * Browser code never sees a token: dashboard API calls go through the
 * same-origin `/api/sf/*` route, which attaches the bearer token (refreshing it
 * when it is about to expire).
 *
 * Local development without WorkOS: set `SF_DEV_API_KEY` (or
 * `NEXT_PUBLIC_SF_DEV_API_KEY`) to an API key; the proxy then sends that key
 * instead of a session, and sign-in is skipped.
 */

export const SESSION_COOKIE = "sf_session";
export const STATE_COOKIE = "sf_auth_state";
const WORKOS_API = process.env.WORKOS_API_URL ?? "https://api.workos.com";
const REFRESH_MARGIN_S = 60;

export interface Session {
	access_token: string;
	organization_id?: string | null;
	refresh_token: string;
	user: {
		email: string;
		first_name?: string | null;
		id: string;
		last_name?: string | null;
	};
}

export function devApiKey(): string | undefined {
	return (
		process.env.SF_DEV_API_KEY ||
		process.env.NEXT_PUBLIC_SF_DEV_API_KEY ||
		undefined
	);
}

export function workosConfigured(): boolean {
	return Boolean(
		process.env.WORKOS_CLIENT_ID &&
			process.env.WORKOS_API_KEY &&
			process.env.WORKOS_COOKIE_PASSWORD
	);
}

const PADDING = /[=]+$/u;

function b64url(bytes: Uint8Array): string {
	let s = "";
	for (const b of bytes) {
		s += String.fromCharCode(b);
	}
	return btoa(s).replaceAll("+", "-").replaceAll("/", "_").replace(PADDING, "");
}

function unb64url(value: string): Uint8Array {
	const padded =
		value.replaceAll("-", "+").replaceAll("_", "/") +
		"=".repeat((4 - (value.length % 4)) % 4);
	const bin = atob(padded);
	const out = new Uint8Array(bin.length);
	for (let i = 0; i < bin.length; i += 1) {
		out[i] = bin.charCodeAt(i);
	}
	return out;
}

async function key(): Promise<CryptoKey> {
	const password = process.env.WORKOS_COOKIE_PASSWORD;
	if (!password || password.length < 32) {
		throw new Error("WORKOS_COOKIE_PASSWORD must be at least 32 characters");
	}
	const digest = await crypto.subtle.digest(
		"SHA-256",
		new TextEncoder().encode(password)
	);
	return crypto.subtle.importKey("raw", digest, "AES-GCM", false, [
		"encrypt",
		"decrypt",
	]);
}

export async function seal(value: unknown): Promise<string> {
	const iv = crypto.getRandomValues(new Uint8Array(12));
	const data = new TextEncoder().encode(JSON.stringify(value));
	const ct = new Uint8Array(
		await crypto.subtle.encrypt({ iv, name: "AES-GCM" }, await key(), data)
	);
	const out = new Uint8Array(iv.length + ct.length);
	out.set(iv);
	out.set(ct, iv.length);
	return b64url(out);
}

export async function unseal<T>(value: string | undefined): Promise<T | null> {
	if (!value) {
		return null;
	}
	try {
		const raw = unb64url(value);
		const pt = await crypto.subtle.decrypt(
			{ iv: raw.slice(0, 12), name: "AES-GCM" },
			await key(),
			raw.slice(12)
		);
		return JSON.parse(new TextDecoder().decode(pt)) as T;
	} catch {
		return null;
	}
}

/** The `exp` claim of a JWT, in seconds, without verifying it (the API does). */
export function jwtClaims(token: string): Record<string, unknown> {
	try {
		const payload = token.split(".")[1] ?? "";
		return JSON.parse(new TextDecoder().decode(unb64url(payload))) as Record<
			string,
			unknown
		>;
	} catch {
		return {};
	}
}

export function authorizeUrl(
	redirectUri: string,
	state: string,
	screenHint?: string
): string {
	const q = new URLSearchParams({
		client_id: process.env.WORKOS_CLIENT_ID ?? "",
		provider: "authkit",
		redirect_uri: redirectUri,
		response_type: "code",
		state,
	});
	if (screenHint) {
		q.set("screen_hint", screenHint);
	}
	return `${WORKOS_API}/user_management/authorize?${q}`;
}

async function authenticate(grant: Record<string, string>): Promise<Session> {
	const res = await fetch(`${WORKOS_API}/user_management/authenticate`, {
		body: JSON.stringify({
			client_id: process.env.WORKOS_CLIENT_ID,
			client_secret: process.env.WORKOS_API_KEY,
			...grant,
		}),
		cache: "no-store",
		headers: { "content-type": "application/json" },
		method: "POST",
	});
	if (!res.ok) {
		const body = await res.text();
		throw new Error(
			`WorkOS authenticate failed (${res.status}): ${body.slice(0, 200)}`
		);
	}
	const data = (await res.json()) as Session;
	return {
		access_token: data.access_token,
		organization_id: data.organization_id ?? null,
		refresh_token: data.refresh_token,
		user: {
			email: data.user.email,
			first_name: data.user.first_name,
			id: data.user.id,
			last_name: data.user.last_name,
		},
	};
}

export function exchangeCode(code: string): Promise<Session> {
	return authenticate({ code, grant_type: "authorization_code" });
}

/**
 * A session whose access token is good for at least a minute, refreshing it
 * with the rotating refresh token when needed. Returns `[session, changed]`.
 */
export async function freshSession(
	session: Session
): Promise<[Session, boolean]> {
	const exp = Number(jwtClaims(session.access_token).exp ?? 0);
	if (exp - Date.now() / 1000 > REFRESH_MARGIN_S) {
		return [session, false];
	}
	const next = await authenticate({
		grant_type: "refresh_token",
		refresh_token: session.refresh_token,
	});
	return [next, true];
}

export const COOKIE_OPTIONS = {
	httpOnly: true,
	maxAge: 60 * 60 * 24 * 30,
	path: "/",
	sameSite: "lax" as const,
	secure: process.env.NODE_ENV === "production",
};

export function logoutUrl(session: Session | null, returnTo: string): string {
	const sid = session ? jwtClaims(session.access_token).sid : undefined;
	if (typeof sid !== "string") {
		return returnTo;
	}
	const q = new URLSearchParams({ return_to: returnTo, session_id: sid });
	return `${WORKOS_API}/user_management/sessions/logout?${q}`;
}
