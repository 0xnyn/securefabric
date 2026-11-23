/** Usage numbers for the Overview and Metrics pages. The stored operations
 * are a sample; these series scale them up to the traffic an environment of
 * this size would see, deterministically, so charts don't jump on rerender.
 * Requests made in the playground are added on top as they happen. */

import { createRng } from "./random";
import type { Environment, Operation } from "./types";

export type Range = "24h" | "7d" | "30d";

/** Shortest first. Object keys get sorted by the formatter, so lists of
 * ranges come from here, never from `Object.keys(RANGE_LABELS)`. */
export const RANGES: readonly Range[] = ["24h", "7d", "30d"];

export const RANGE_LABELS: Record<Range, string> = {
	"7d": "Last 7 days",
	"24h": "Last 24 hours",
	"30d": "Last 30 days",
};

const HOUR = 3_600_000;
const DAY = 24 * HOUR;

export const RANGE_CONFIG: Record<Range, { bucket: number; buckets: number }> =
	{
		"7d": { bucket: 6 * HOUR, buckets: 28 },
		"24h": { bucket: HOUR, buckets: 24 },
		"30d": { bucket: DAY, buckets: 30 },
	};

export interface Bucket {
	errors: number;
	records: number;
	requests: number;
	start: number;
	syncFailures: number;
	syncs: number;
}

function diurnal(t: number): number {
	const hour = new Date(t).getUTCHours();
	const weekday = new Date(t).getUTCDay();
	const weekend = weekday === 0 || weekday === 6 ? 0.55 : 1;
	return (
		(0.45 + 0.55 * Math.sin(((hour - 8) / 24) * Math.PI * 2) ** 2) * weekend
	);
}

/** API requests per hour for an environment this size, before noise. */
function baseRate(env: Environment): number {
	const healthy = env.connections.filter(
		(c) => c.health !== "UNAUTHORIZED"
	).length;
	return env.isProduction ? healthy * 46 : healthy * 7;
}

export function buildSeries(
	env: Environment,
	range: Range,
	now = Date.now()
): Bucket[] {
	const { bucket, buckets } = RANGE_CONFIG[range];
	const end = Math.ceil(now / bucket) * bucket;
	const start = end - bucket * buckets;
	const rate = baseRate(env);
	const hoursPerBucket = bucket / HOUR;
	const out: Bucket[] = Array.from({ length: buckets }, (_, i) => {
		const t = start + i * bucket;
		const rng = createRng(`${env.id}:${bucket}:${t}`);
		const noise = 0.8 + rng.next() * 0.4;
		const requests = Math.round(
			rate * hoursPerBucket * diurnal(t + bucket / 2) * noise
		);
		const errorRate = 0.004 + rng.next() * 0.012;
		const connections = env.connections.length;
		const syncs = Math.round(
			connections * hoursPerBucket * (env.isProduction ? 1.6 : 1.1) * noise
		);
		return {
			errors: Math.round(requests * errorRate),
			records: Math.round(syncs * (180 + rng.next() * 900)),
			requests,
			start: t,
			syncFailures: rng.bool(0.25)
				? rng.int(0, Math.max(1, Math.round(syncs * 0.04)))
				: 0,
			syncs,
		};
	});
	// Live operations from this session land on top of the baseline.
	for (const op of env.operations) {
		if (
			op.startedAt < start ||
			op.startedAt >= end ||
			op.startedAt < env.createdAt
		) {
			continue;
		}
		if (now - op.startedAt > 2 * HOUR) {
			continue;
		}
		const index = Math.floor((op.startedAt - start) / bucket);
		const b = out[index];
		if (!b) {
			continue;
		}
		addOp(b, op);
	}
	if (env.connections.length === 0) {
		return out.map((b) => ({
			...b,
			errors: 0,
			records: 0,
			requests: 0,
			syncFailures: 0,
			syncs: 0,
		}));
	}
	return out;
}

function addOp(b: Bucket, op: Operation): void {
	if (op.type === "api" || op.type === "proxy" || op.type === "action") {
		b.requests += 1;
		if (op.status === "failed") {
			b.errors += 1;
		}
	}
	if (op.type === "sync") {
		b.syncs += 1;
		b.records += op.records ?? 0;
		if (op.status === "failed") {
			b.syncFailures += 1;
		}
	}
}

export interface Totals {
	errorRate: number;
	errors: number;
	p50: number;
	p95: number;
	records: number;
	requests: number;
	syncSuccess: number;
	syncs: number;
}

export function totals(series: Bucket[], env: Environment): Totals {
	const sum = (k: keyof Bucket): number => series.reduce((a, b) => a + b[k], 0);
	const requests = sum("requests");
	const errors = sum("errors");
	const syncs = sum("syncs");
	const failures = sum("syncFailures");
	const latencies = env.operations
		.filter((o) => o.type === "api")
		.map((o) => o.durationMs)
		.sort((a, b) => a - b);
	const at = (q: number): number =>
		latencies[Math.floor(latencies.length * q)] ?? 0;
	return {
		errorRate: requests ? errors / requests : 0,
		errors,
		p50: at(0.5),
		p95: at(0.95),
		records: sum("records"),
		requests,
		syncSuccess: syncs ? 1 - failures / syncs : 1,
		syncs,
	};
}

/** Share of traffic per key (endpoint, integration), from the sampled ops. */
export function breakdown(
	ops: Operation[],
	key: (op: Operation) => string | null,
	scale: number
): { key: string; value: number }[] {
	const counts = new Map<string, number>();
	for (const op of ops) {
		const k = key(op);
		if (k) {
			counts.set(k, (counts.get(k) ?? 0) + 1);
		}
	}
	const total = [...counts.values()].reduce((a, b) => a + b, 0) || 1;
	return [...counts.entries()]
		.map(([k, v]) => ({ key: k, value: Math.round((v / total) * scale) }))
		.sort((a, b) => b.value - a.value);
}
