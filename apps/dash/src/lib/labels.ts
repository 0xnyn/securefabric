/** "REOPENED" → "Reopened", "sync_bulk" → "Sync bulk": an enum in sentence case. */
export function humanize(value: string): string {
	const words = value.replaceAll("_", " ").toLowerCase();
	return words.charAt(0).toUpperCase() + words.slice(1);
}

/** How a sync ran (schema Mode / SyncMode), as it reads after a stream name. */
const SYNC_MODES: Record<string, string> = {
	backfill: "first full sync",
	export: "bulk export",
	full: "full read",
	incremental: "changes only",
	targeted: "targeted refresh",
};

/** A sync operation's action is `stream:mode`: "Vulnerability findings · changes only". */
export function syncActionLabel(action: string): string {
	const [stream, mode] = action.split(":");
	if (!(stream && mode)) {
		return humanize(action);
	}
	return `${humanize(stream)} · ${SYNC_MODES[mode] ?? mode}`;
}
