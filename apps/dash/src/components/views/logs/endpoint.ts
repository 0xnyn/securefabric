import { createLoader } from "nuqs";
import SuperJSON from "superjson";
import type {
	FacetMetadataSchema,
	InfiniteQueryResponse,
} from "@/lib/data-table";
import { bucketChartData } from "@/lib/data-table/chart-data";
import { defineFilters } from "@/lib/filters";
import { simulateLiveTraffic } from "@/lib/simulate-traffic";
import { readWorkspace } from "@/lib/store";
import { PAGE_SIZE, type SearchParams, searchParamsParser } from "./schema";
import { LEVELS, type LogRow, tableSchema, toLogRow } from "./table-schema";

/**
 * The logs API, answered in the browser.
 *
 * The playground has no server: its workspace lives in localStorage. Rather
 * than give the table a different code path, this is a `fetch` that speaks
 * the same contract as the registry's route handler (and the real SecureFabric
 * API): `GET /{env}/logs/api?…filters` → `{ data, meta, prevCursor,
 * nextCursor }`, SuperJSON-encoded. The table, its query layer and the URL
 * state are the stock data-table-filters blocks; pointing them at a real
 * endpoint means deleting this file and the `transport.fetch` line.
 */

const filters = defineFilters(tableSchema.definition);
const loadSearch = createLoader(searchParamsParser);

const sliderKeys = filters.specs
	.filter((spec) => spec.type === "slider")
	.map((spec) => spec.key);
const dateKeys = filters.specs
	.filter((spec) => spec.type === "timerange")
	.map((spec) => spec.key);
const facetKeys = filters.specs
	.filter((spec) => spec.type !== "timerange" && spec.type !== "slider")
	.map((spec) => spec.key);

function compare(left: unknown, right: unknown): number {
	const a = left instanceof Date ? left.getTime() : left;
	const b = right instanceof Date ? right.getTime() : right;
	if (typeof a === "number" && typeof b === "number") {
		return a - b;
	}
	return String(a ?? "").localeCompare(String(b ?? ""));
}

/** Newest first, the order a timestamp cursor addresses. The requested sort
 * only breaks ties between rows sharing a timestamp. */
function sortRows(rows: LogRow[], sort: SearchParams["sort"]): LogRow[] {
	const key = sort?.id as keyof LogRow | undefined;
	const direction = sort?.desc ? -1 : 1;
	return [...rows].sort(
		(a, b) =>
			compare(b.date, a.date) ||
			(key ? compare(a[key], b[key]) * direction : 0) ||
			compare(b.uuid, a.uuid)
	);
}

/** One page by timestamp cursor. `next` reads older rows; `prev` reads
 * everything newer, which is what live mode polls for. */
function pageRows(rows: LogRow[], search: SearchParams): LogRow[] {
	const cursor = search.cursor?.getTime() ?? Date.now();
	const size = search.size && search.size > 0 ? search.size : PAGE_SIZE;
	if (search.direction === "prev") {
		return rows.filter((row) => row.date.getTime() > cursor);
	}
	const page: LogRow[] = [];
	for (const row of rows) {
		const time = row.date.getTime();
		if (time >= cursor) {
			continue;
		}
		const last = page.at(-1);
		if (page.length < size || last?.date.getTime() === time) {
			page.push(row);
		} else {
			break;
		}
	}
	return page;
}

function facetsOf(
	rows: LogRow[],
	keys: string[]
): Record<string, FacetMetadataSchema> {
	const facets: Record<string, FacetMetadataSchema> = {};
	for (const key of keys) {
		const counts = new Map<unknown, number>();
		let min: number | undefined;
		let max: number | undefined;
		for (const row of rows) {
			const value = row[key as keyof LogRow];
			if (value === null || value === undefined) {
				continue;
			}
			counts.set(value, (counts.get(value) ?? 0) + 1);
			if (typeof value === "number") {
				min = min === undefined ? value : Math.min(min, value);
				max = max === undefined ? value : Math.max(max, value);
			}
		}
		facets[key] = {
			max,
			min,
			rows: [...counts].map(([value, total]) => ({ total, value })),
			total: rows.length,
		};
	}
	return facets;
}

function respond(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		headers: { "content-type": "application/json" },
		status,
	});
}

/** Matches "Operations are kept for 15 days" in the logs footer. */
const RETENTION_MS = 15 * 24 * 60 * 60 * 1000;

export function handleLogsRequest(input: RequestInfo | URL): Response {
	const url = new URL(
		input instanceof Request ? input.url : String(input),
		window.location.origin
	);
	const [, slug = ""] = url.pathname.split("/");
	// Only live mode asks for newer rows ("prev"), so this is a live poll. It
	// runs before the workspace is read, so the poll sees what it logged.
	if (url.searchParams.get("direction") === "prev") {
		simulateLiveTraffic(slug);
	}
	const env = readWorkspace()?.environments.find((e) => e.slug === slug);
	if (!env) {
		return respond({ error: `No environment "${slug}"` }, 404);
	}

	const search = loadSearch(url);
	const values = search as Record<string, unknown>;
	// Retention: older operations (the auth events from when a connection was
	// first made, months back) would stretch the timeline to fit them.
	const retainedFrom = Date.now() - RETENTION_MS;
	const rows = env.operations
		.map(toLogRow)
		.filter((row) => row.date.getTime() >= retainedFrom);

	// Three passes, as in the registry handler: the date range, then every
	// filter but the sliders, then the sliders, so a slider's facet range
	// stays visible after the user narrows it.
	const ranged = filters.apply(rows, values, { only: dateKeys });
	const withoutSliders = filters.apply(ranged, values, {
		exclude: [...sliderKeys, ...dateKeys],
	});
	const filtered = filters.apply(withoutSliders, values, { only: sliderKeys });
	const page = pageRows(sortRows(filtered, search.sort), search);

	const skipMeta = url.searchParams.get("_meta") === "false";
	const response: InfiniteQueryResponse<LogRow[]> = {
		data: page,
		meta: {
			chartData: skipMeta
				? []
				: bucketChartData(filtered, {
						keys: LEVELS,
						range: search.date,
						series: (row) => row.level,
						timestamp: (row) => row.date,
					}),
			facets: skipMeta
				? {}
				: {
						...facetsOf(withoutSliders, sliderKeys),
						...facetsOf(filtered, facetKeys),
					},
			filterRowCount: filtered.length,
			totalRowCount: rows.length,
		},
		nextCursor: page.at(-1)?.date.getTime() ?? null,
		// Never null: live mode pages "prev" from the first page's cursor, and a
		// null after one empty poll would stop it for good. An empty page keeps
		// the cursor it was asked for, so nothing logged meanwhile is skipped.
		prevCursor:
			page[0]?.date.getTime() ?? search.cursor?.getTime() ?? Date.now(),
	};
	return respond(SuperJSON.stringify(response));
}

/** A `fetch` that answers logs requests from the store, for `transport`. */
export const logsFetch: typeof fetch = (input) =>
	Promise.resolve(handleLogsRequest(input));
