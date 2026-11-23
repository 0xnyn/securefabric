import {
	AlertTriangleIcon,
	ArrowLeftRightIcon,
	KeyRoundIcon,
	ListIcon,
	type LucideIcon,
	RefreshCwIcon,
	TimerIcon,
	WebhookIcon,
} from "lucide-react";

/**
 * Saved views of the logs table. A view is a query string over the table's
 * URL state (components/views/logs/schema.ts), so it costs nothing to add one
 * and the sidebar, the palette and a pasted link all open the same thing.
 */
export interface LogView {
	description: string;
	icon: LucideIcon;
	id: string;
	label: string;
	/** Without the leading "?"; empty for the unfiltered table. */
	query: string;
}

export const LOG_VIEWS: LogView[] = [
	{
		description: "Every operation in the last 15 days",
		icon: ListIcon,
		id: "all",
		label: "All operations",
		query: "",
	},
	{
		description: "Failed syncs, API errors and webhook failures",
		icon: AlertTriangleIcon,
		id: "errors",
		label: "Errors",
		query: "level=error",
	},
	{
		description: "Scheduled and initial syncs",
		icon: RefreshCwIcon,
		id: "syncs",
		label: "Syncs",
		query: "type=sync",
	},
	{
		description: "Unified API and passthrough requests",
		icon: ArrowLeftRightIcon,
		id: "api",
		label: "API requests",
		query: "type=api,proxy",
	},
	{
		description: "Deliveries to your webhook endpoints",
		icon: WebhookIcon,
		id: "webhooks",
		label: "Webhooks",
		query: "type=webhook",
	},
	{
		description: "Connects, reconnects and revoked credentials",
		icon: KeyRoundIcon,
		id: "auth",
		label: "Auth events",
		query: "type=auth",
	},
	{
		description: "Operations that took longer than two seconds",
		icon: TimerIcon,
		id: "slow",
		label: "Slow operations",
		query: "latency=2000-30000",
	},
];

/** The view a query string is exactly, ignoring the open row and paging. */
export function activeLogView(search: URLSearchParams): string | null {
	const params = new URLSearchParams(search);
	for (const key of ["uuid", "cursor", "direction", "size", "live", "sort"]) {
		params.delete(key);
	}
	const current = decodeURIComponent(params.toString());
	return LOG_VIEWS.find((v) => v.query === current)?.id ?? null;
}
