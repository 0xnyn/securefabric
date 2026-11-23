const INTERVALS: readonly { thresholdMinutes: number; intervalMs: number }[] = [
	{ intervalMs: 1000, thresholdMinutes: 1 }, // 1 second
	{ intervalMs: 5000, thresholdMinutes: 5 }, // 5 seconds
	{ intervalMs: 10_000, thresholdMinutes: 10 }, // 10 seconds
	{ intervalMs: 30_000, thresholdMinutes: 30 }, // 30 seconds
	{ intervalMs: 60_000, thresholdMinutes: 60 }, // 1 minute
	{ intervalMs: 120_000, thresholdMinutes: 120 }, // 2 minutes
	{ intervalMs: 240_000, thresholdMinutes: 240 }, // 4 minutes
	{ intervalMs: 480_000, thresholdMinutes: 480 }, // 8 minutes
	{ intervalMs: 1_440_000, thresholdMinutes: 1440 }, // 24 minutes
	{ intervalMs: 2_880_000, thresholdMinutes: 2880 }, // 48 minutes
	{ intervalMs: 5_760_000, thresholdMinutes: 5760 }, // 96 minutes
	{ intervalMs: 11_520_000, thresholdMinutes: 11_520 }, // 192 minutes
	{ intervalMs: 23_040_000, thresholdMinutes: 23_040 }, // 384 minutes
];

/** The bucket used for any range longer than the last threshold. */
const MAX_INTERVAL_MS = 46_080_000; // 768 minutes

/**
 * Pick a bucket size for a range of `durationMs`.
 *
 * Negative durations are treated as their absolute value, so callers do not
 * have to order the bounds first.
 */
export function evaluateIntervalMs(durationMs: number): number {
	if (!Number.isFinite(durationMs)) {
		return MAX_INTERVAL_MS;
	}
	const durationMinutes = Math.abs(durationMs) / 60_000;
	for (const { thresholdMinutes, intervalMs } of INTERVALS) {
		if (durationMinutes < thresholdMinutes) {
			return intervalMs;
		}
	}
	return MAX_INTERVAL_MS;
}
