import { HealthBadge, ProviderLogo } from "@/components/common";
import type { Option } from "@/components/data-table/types";
import { getProvider, PROVIDERS } from "@/lib/catalog";
import {
	col,
	createTableSchema,
	type InferTableType,
} from "@/lib/table-schema";
import { type Connection, HEALTH, type HealthCode } from "@/lib/types";

/**
 * Status as people filter by it, coarser than the health code: "needs
 * attention" covers four codes that all mean "someone has to act". The
 * sidebar's views link to these values (`?status=attention`).
 */
export const CONNECTION_STATUSES = [
	"healthy",
	"attention",
	"syncing",
	"paused",
] as const;
export type ConnectionStatus = (typeof CONNECTION_STATUSES)[number];

const STATUS_LABELS: Record<ConnectionStatus, string> = {
	attention: "Needs attention",
	healthy: "Healthy",
	paused: "Paused",
	syncing: "Syncing",
};

export const CONNECTION_KINDS = ["live", "sandbox"] as const;

const RECORDS_MAX = 500_000;

export function statusOf(conn: Connection): ConnectionStatus {
	if (conn.paused) {
		return "paused";
	}
	if (conn.health === "SYNCING") {
		return "syncing";
	}
	const { tone } = HEALTH[conn.health];
	return tone === "error" || tone === "warn" ? "attention" : "healthy";
}

const PROVIDER_SLUGS = PROVIDERS.map((p) => p.slug) as [string, ...string[]];

function ProviderOption({ value }: Option) {
	const slug = String(value);
	return (
		<span className="flex min-w-0 items-center gap-2">
			<ProviderLogo provider={slug} size={16} />
			<span className="truncate">{getProvider(slug)?.name ?? slug}</span>
		</span>
	);
}

function CustomerCell({ row }: { row: ConnectionRow }) {
	return (
		<span className="flex min-w-0 items-center gap-2.5">
			<ProviderLogo provider={row.provider} size={20} />
			<span className="grid min-w-0 leading-tight">
				<span className="truncate font-medium">{row.customer}</span>
				<span className="text-muted-foreground truncate text-xs">
					{row.email}
				</span>
			</span>
		</span>
	);
}

/**
 * The connections table: columns, filter rail, filter command and row sheet
 * all come from this one definition, as on the logs table. Client-side this
 * time: an environment has tens of connections, not thousands of log lines,
 * so the table filters and paginates in memory.
 */
// biome-ignore assist/source/useSortedKeys: key order is the default column order.
export const tableSchema = createTableSchema({
	select: col.select(),
	customer: col
		.string()
		.label("Customer")
		.display("custom", {
			cell: (_value: unknown, row: unknown) => (
				<CustomerCell row={row as ConnectionRow} />
			),
		})
		.filterable("input")
		.minSize(240)
		.sheet(),
	status: col
		.enum(CONNECTION_STATUSES)
		.label("Status")
		.display("custom", {
			cell: (_value: unknown, row: unknown) => (
				<HealthBadge health={(row as ConnectionRow).health as HealthCode} />
			),
		})
		.filterable("checkbox", {
			options: CONNECTION_STATUSES.map((s) => ({
				label: STATUS_LABELS[s],
				value: s,
			})),
		})
		.defaultOpen()
		.size(160)
		.sheet(),
	provider: col
		.enum(PROVIDER_SLUGS)
		.label("Tool")
		.display("custom", {
			cell: (value: unknown) => (
				<span className="truncate">
					{getProvider(String(value))?.name ?? String(value)}
				</span>
			),
		})
		// Filled from the tools that appear, not the whole catalog.
		.filterable("checkbox", { component: ProviderOption, options: [] })
		.defaultOpen()
		// The customer cell already shows the tool's logo; the column is for
		// people who want the name spelled out.
		.hidden()
		.size(150)
		.sheet(),
	kind: col
		.enum(CONNECTION_KINDS)
		.label("Type")
		.display("badge")
		.filterable("checkbox", {
			options: [
				{ label: "Live", value: "live" },
				{ label: "Sandbox", value: "sandbox" },
			],
		})
		.size(96)
		.sheet(),
	records: col
		.number()
		.label("Records")
		.display("number")
		.filterable("slider", { max: RECORDS_MAX, min: 0 })
		.size(110)
		.sheet(),
	lastSync: col.presets
		.timestamp()
		.label("Last sync")
		.optional()
		.size(180)
		.sheet(),
	created: col.presets.timestamp().label("Created").hidden().size(180).sheet(),
	integration: col
		.string()
		.label("Integration")
		.display("code")
		.filterable("input")
		.hidden()
		.size(160)
		.sheet(),
	email: col
		.string()
		.label("Email")
		.filterable("input")
		.hidden()
		.size(200)
		.sheet(),
	id: col
		.string()
		.label("Connection ID")
		.display("code")
		.filterable("input")
		.hidden()
		.size(170)
		.sheet(),
});

export type ConnectionRow = InferTableType<typeof tableSchema.definition> & {
	/** Not a column: the badge reads it to show the exact health code. */
	health: HealthCode;
};

export function totalRecords(conn: Connection): number {
	return Object.values(conn.counts).reduce((a, b) => a + (b ?? 0), 0);
}

export function toConnectionRow(conn: Connection): ConnectionRow {
	return {
		created: new Date(conn.createdAt),
		customer: conn.customer.orgName,
		email: conn.customer.email,
		health: conn.health,
		id: conn.id,
		integration: conn.integrationId,
		kind: conn.sandbox ? "sandbox" : "live",
		lastSync: conn.lastSyncAt ? new Date(conn.lastSyncAt) : undefined,
		provider: conn.provider,
		records: totalRecords(conn),
		select: false,
		status: statusOf(conn),
	};
}
