const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export function timeAgo(ms: number | null, now = Date.now()): string {
	if (ms === null) {
		return "Never";
	}
	const diff = now - ms;
	if (diff < 0) {
		return `in ${duration(-diff)}`;
	}
	if (diff < 45 * SECOND) {
		return "just now";
	}
	if (diff < HOUR) {
		return `${Math.round(diff / MINUTE)}m ago`;
	}
	if (diff < DAY) {
		return `${Math.round(diff / HOUR)}h ago`;
	}
	if (diff < 30 * DAY) {
		return `${Math.round(diff / DAY)}d ago`;
	}
	return dateShort(ms);
}

export function duration(ms: number): string {
	if (ms < SECOND) {
		return `${Math.round(ms)}ms`;
	}
	if (ms < MINUTE - SECOND / 2) {
		return `${(ms / SECOND).toFixed(ms < 10 * SECOND ? 1 : 0)}s`;
	}
	const totalSeconds = Math.round(ms / SECOND);
	if (totalSeconds < 3600) {
		const m = Math.floor(totalSeconds / 60);
		const s = totalSeconds % 60;
		return s ? `${m}m ${s}s` : `${m}m`;
	}
	const totalMinutes = Math.round(ms / MINUTE);
	const h = Math.floor(totalMinutes / 60);
	const m = totalMinutes % 60;
	return m ? `${h}h ${m}m` : `${h}h`;
}

const SHORT = new Intl.DateTimeFormat("en-US", {
	day: "numeric",
	month: "short",
});
const FULL = new Intl.DateTimeFormat("en-US", {
	day: "numeric",
	hour: "2-digit",
	minute: "2-digit",
	month: "short",
	second: "2-digit",
});
const TIME = new Intl.DateTimeFormat("en-US", {
	hour: "2-digit",
	hour12: false,
	minute: "2-digit",
	second: "2-digit",
});

export function dateShort(ms: number): string {
	return SHORT.format(ms);
}

export function dateTime(ms: number): string {
	return FULL.format(ms);
}

export function clock(ms: number): string {
	return TIME.format(ms);
}

const COMPACT = new Intl.NumberFormat("en-US", {
	maximumFractionDigits: 1,
	notation: "compact",
});
const PLAIN = new Intl.NumberFormat("en-US");

export function compact(n: number): string {
	return COMPACT.format(n);
}

export function num(n: number): string {
	return PLAIN.format(n);
}

export function pct(n: number, digits = 1): string {
	return `${(n * 100).toFixed(digits)}%`;
}

export function mask(value: string, visible = 4): string {
	if (value.length <= visible) {
		return "••••";
	}
	return `${value.slice(0, Math.min(8, value.length - visible))}${"•".repeat(12)}${value.slice(-visible)}`;
}

export function plural(
	n: number,
	word: string,
	pluralWord = `${word}s`
): string {
	return `${num(n)} ${n === 1 ? word : pluralWord}`;
}
