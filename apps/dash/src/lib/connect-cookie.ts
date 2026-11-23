/**
 * The hosted connect flow's credential: the `sfcs_` session token from the
 * link, moved out of the URL into an httpOnly cookie scoped to `/connect`
 * (part 8, section 5). It never reaches page JavaScript, history or referrers.
 *
 * The page is usually framed by connect-js on the customer's site, so over
 * HTTPS the cookie is `SameSite=None; Secure; Partitioned` (CHIPS): it is
 * readable only inside that embedding, which is all it needs.
 */
export const CONNECT_COOKIE = "sf_connect";

export const TOKEN_PATTERN = /^sfcs_[A-Za-z0-9_-]{16,128}$/u;

export function connectCookie(token: string, secure: boolean): string {
	const parts = [
		`${CONNECT_COOKIE}=${token}`,
		"Path=/connect",
		"HttpOnly",
		"Max-Age=3600",
		secure ? "SameSite=None" : "SameSite=Lax",
	];
	if (secure) {
		parts.push("Secure", "Partitioned");
	}
	return parts.join("; ");
}
