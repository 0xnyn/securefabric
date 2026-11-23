import { ENDPOINTS } from "@/lib/endpoints";
import { logOperation, readWorkspace } from "@/lib/store";

/**
 * Requests "your app" makes while live mode watches the logs.
 *
 * In production, live mode shows traffic that is already happening. The
 * playground has no traffic of its own: nothing calls its API while you
 * watch. Each live poll therefore logs a few plausible requests against the
 * environment's healthy connections, so the stream behaves like the real
 * one. Mostly successes, an occasional 4xx/5xx, and latencies with a tail.
 */

const MAX_PER_POLL = 3;
const ERROR_RATE = 0.06;
const ERROR_CODES = [400, 401, 404, 429, 502] as const;

function pick<T>(items: readonly T[]): T | undefined {
	return items[Math.floor(Math.random() * items.length)];
}

/** Log-normal-ish: most requests are fast, a few are slow. */
function latency(): number {
	const base = 90 + Math.random() * 220;
	return Math.round(
		Math.random() < 0.08 ? base * (4 + Math.random() * 6) : base
	);
}

export function simulateLiveTraffic(slug: string): void {
	const env = readWorkspace()?.environments.find((e) => e.slug === slug);
	if (!env) {
		return;
	}
	const connections = env.connections.filter(
		(c) => !c.paused && c.health !== "UNAUTHORIZED"
	);
	const endpoints = ENDPOINTS.filter(
		(e) => e.method === "GET" && e.kind !== "connections"
	);
	const count = Math.floor(Math.random() * (MAX_PER_POLL + 1));
	for (let i = 0; i < count; i += 1) {
		const conn = pick(connections);
		const endpoint = pick(endpoints);
		if (!(conn && endpoint)) {
			return;
		}
		const failed = Math.random() < ERROR_RATE;
		const statusCode = failed ? (pick(ERROR_CODES) ?? 500) : 200;
		const path = endpoint.path.replace(
			"{id}",
			`${endpoint.model ?? "rec"}_live`
		);
		logOperation(slug, conn.id, {
			action: `GET ${path}`,
			durationMs: latency(),
			method: "GET",
			path,
			records: failed ? 0 : Math.floor(Math.random() * 100),
			status: failed ? "failed" : "success",
			statusCode,
			type: "api",
		});
	}
}
