import { ProviderLogo } from "@/components/common";
import type { Option } from "@/components/data-table/types";
import { getProvider, PROVIDERS } from "@/lib/catalog";
import {
	col,
	createTableSchema,
	type InferTableType,
} from "@/lib/table-schema";
import type { Operation, OperationType } from "@/lib/types";
import { OP_TYPE_LABELS, opTitle } from "../shared";

export const LEVELS = ["error", "warning", "info"] as const;
export type Level = (typeof LEVELS)[number];

export const OP_TYPES = [
	"api",
	"sync",
	"auth",
	"webhook",
	"proxy",
	"action",
] as const satisfies readonly OperationType[];

const STATUS_CODES = [
	200, 201, 202, 204, 400, 401, 403, 404, 409, 422, 429, 500, 502, 503,
];

/** Durations in the playground top out around half a minute (initial syncs). */
const DURATION_MAX_MS = 30_000;
const RECORDS_MAX = 5000;

/**
 * The tint on the rows worth noticing, stepping up on hover, focus and for
 * the row open in the sheet. Successful rows are nearly all of them, so they
 * stay plain. Mirrors the registry example's `getLevelRowClassName`.
 */
export function levelRowClassName(level: Level): string {
	switch (level) {
		case "warning":
			return "bg-warning/5 hover:bg-warning/10 focus-visible:bg-warning/10 data-[state=selected]:bg-warning/20 dark:bg-warning/10 dark:hover:bg-warning/20 dark:data-[state=selected]:bg-warning/30";
		case "error":
			return "bg-error/5 hover:bg-error/10 focus-visible:bg-error/10 data-[state=selected]:bg-error/20 dark:bg-error/10 dark:hover:bg-error/20 dark:data-[state=selected]:bg-error/30";
		default:
			return "";
	}
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

function OperationCell({ row }: { row: LogRow }) {
	return (
		<span className="flex min-w-0 items-center gap-2">
			{row.provider ? <ProviderLogo provider={row.provider} size={18} /> : null}
			<span className="text-code truncate font-mono">{row.operation}</span>
		</span>
	);
}

/**
 * The one definition the logs table reads from: columns, the filter rail, the
 * filter command, the row sheet, the URL state and the in-browser endpoint's
 * filter semantics are all generated from it.
 */
// biome-ignore assist/source/useSortedKeys: key order is the default column order.
export const tableSchema = createTableSchema({
	level: col.presets
		.logLevel(LEVELS)
		.label("Level")
		.display("level-indicator")
		.hideHeader()
		.size(37)
		.sheet(),
	date: col.presets
		.timestamp()
		.label("Date")
		// The endpoint pages newest-first by a timestamp cursor; sorting by
		// date would promise an order it can't deliver across pages.
		.sortable(false)
		.defaultOpen()
		.commandDisabled()
		.size(190)
		.sheet(),
	// Integration ids are per-environment, so a text filter: an enum's URL
	// parser would reject any id it wasn't built with.
	type: col
		.enum(OP_TYPES)
		.label("Type")
		.display("badge")
		.filterable("checkbox", {
			options: OP_TYPES.map((t) => ({ label: OP_TYPE_LABELS[t], value: t })),
		})
		.defaultOpen()
		.size(96)
		.sheet(),
	operation: col
		.string()
		.label("Operation")
		.display("custom", {
			cell: (_value: unknown, row: unknown) => (
				<OperationCell row={row as LogRow} />
			),
		})
		.filterable("input")
		// The one unsized column: it absorbs the table's leftover width.
		.minSize(260)
		.sheet(),
	status: col.presets.httpStatus(STATUS_CODES).optional().size(76).sheet(),
	integration: col
		.string()
		.label("Integration")
		.display("code")
		.filterable("input")
		.optional()
		.size(170)
		.sheet(),
	customer: col
		.string()
		.label("Customer")
		.filterable("input")
		.optional()
		.size(170)
		.sheet(),
	latency: col.presets
		.latency("ms", { max: DURATION_MAX_MS, min: 0 })
		.label("Duration")
		.size(110)
		.sheet(),
	records: col
		.number()
		.label("Records")
		.display("number")
		.filterable("slider", { max: RECORDS_MAX, min: 0 })
		.optional()
		.hidden()
		.size(100)
		.sheet(),
	provider: col
		.enum(PROVIDER_SLUGS)
		.label("Provider")
		// No options here: `applyFacets` fills them from the providers that
		// actually appear, rather than listing all of the catalog.
		.filterable("checkbox", { component: ProviderOption, options: [] })
		.optional()
		.hidden()
		.size(130)
		.sheet(),
	connection: col
		.string()
		.label("Connection")
		.display("code")
		.filterable("input")
		.optional()
		.hidden()
		.size(170)
		.sheet(),
	path: col.presets
		.pathname()
		.label("Path")
		.optional()
		.hidden()
		.size(220)
		.sheet(),
	uuid: col.presets.traceId().label("Operation ID").hidden().sheet(),
});

export type LogRow = InferTableType<typeof tableSchema.definition>;

function levelOf(op: Operation): Level {
	if (op.status === "failed") {
		return "error";
	}
	if (op.status === "warning") {
		return "warning";
	}
	return "info";
}

/** An operation as the logs endpoint returns it. */
export function toLogRow(op: Operation): LogRow {
	return {
		connection: op.connectionId ?? undefined,
		customer: op.customer ?? undefined,
		date: new Date(op.startedAt),
		integration: op.integrationId ?? undefined,
		latency: op.durationMs,
		level: levelOf(op),
		operation: opTitle(op),
		path: op.path ?? undefined,
		provider: op.provider ?? undefined,
		records: op.records ?? undefined,
		status: op.statusCode ?? undefined,
		type: op.type,
		uuid: op.id,
	};
}
