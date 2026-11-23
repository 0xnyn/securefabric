"use client";

import { cn } from "@securefabric/ui/lib/utils";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useCallback, useMemo } from "react";
import {
	TimelineChart,
	type TimelineChartSeries,
} from "@/components/data-table/data-table-chart/timeline-chart";
import { DataTableFilterCommand } from "@/components/data-table/data-table-filter-command";
import { DataTableInfinite } from "@/components/data-table/data-table-infinite";
import { LiveButton } from "@/components/data-table/data-table-live/live-button";
import { LiveRow } from "@/components/data-table/data-table-live/live-row";
import { useDataTable } from "@/components/data-table/data-table-provider";
import { DataTableRefreshButton } from "@/components/data-table/data-table-refresh-button";
import { MemoizedDataTableSheetContent } from "@/components/data-table/data-table-sheet/data-table-sheet-content";
import { DataTableSheetDetails } from "@/components/data-table/data-table-sheet/data-table-sheet-details";
import type { SheetField } from "@/components/data-table/types";
import { useEnv, useHref } from "@/components/shell/env-context";
import { ShortcutKeys } from "@/components/shell/shortcut-keys";
import { useLiveMode } from "@/hooks/use-live-mode";
import {
	applyFacets,
	getFacetedMinMaxValues,
	getFacetedUniqueValues,
	getMetaPage,
	refreshDataTableQuery,
} from "@/lib/data-table";
import { isActive } from "@/lib/filters";
import { clock } from "@/lib/format";
import { operationMessages } from "@/lib/log-messages";
import { useNuqsAdapter } from "@/lib/store/adapters/nuqs";
import { useFilterState } from "@/lib/store/hooks/useFilterState";
import { DataTableStoreProvider } from "@/lib/store/provider/DataTableStoreProvider";
import {
	generateColumns,
	generateFilterFields,
	generateSheetFields,
	getDefaultColumnVisibility,
} from "@/lib/table-schema";
import { logsQueryOptions } from "./query-options";
import { type FilterState, filterSchema, STATE_KEYS } from "./schema";
import { type LogRow, levelRowClassName, tableSchema } from "./table-schema";

// Generated once from the schema: columns, the filter rail, the sheet.
const columns = generateColumns<LogRow>(tableSchema.definition);
const baseFilterFields = generateFilterFields<LogRow>(tableSchema.definition);
const sheetFields = generateSheetFields<LogRow>(tableSchema.definition);
const defaultColumnVisibility = getDefaultColumnVisibility(
	tableSchema.definition
);

/** Stacked bottom-up. Colours come from --error/--warning/--info, which
 * index.css points at the design tokens. */
const CHART_SERIES: TimelineChartSeries[] = [
	{ key: "error", label: "Failed" },
	{ key: "warning", label: "Warning" },
	{ key: "info", label: "Succeeded" },
];

const getRowId = (row: LogRow): string => row.uuid;

export function LogsView() {
	const { env } = useEnv();
	const adapter = useNuqsAdapter(filterSchema.definition, { id: "logs" });
	return (
		<DataTableStoreProvider adapter={adapter}>
			{/* Keyed by environment: switching resets the table's internal
			    state (row selection, the loaded pages) with the data. */}
			<LogsTable key={env.slug} />
		</DataTableStoreProvider>
	);
}

function LogsTable() {
	const { env } = useEnv();
	const search = useFilterState<FilterState>();
	const queryClient = useQueryClient();
	const dataOptions = useMemo(() => logsQueryOptions(env.slug), [env.slug]);
	const {
		data,
		isFetching,
		isLoading,
		fetchNextPage,
		fetchPreviousPage,
		hasNextPage,
	} = useInfiniteQuery(dataOptions(search));

	// Not the bare `refetch`: after live mode the first cached page param is a
	// "prev" cursor, and refetching from it would wipe the list.
	const refresh = useCallback(
		() => refreshDataTableQuery(queryClient, dataOptions(search)),
		[queryClient, dataOptions, search]
	);

	const flatData = useMemo(
		// biome-ignore lint/suspicious/noUnnecessaryConditions: `data` is undefined until the first page resolves; Biome's inference misses it.
		() => data?.pages.flatMap((page) => page.data) ?? [],
		[data]
	);
	const liveMode = useLiveMode(flatData);
	const meta = getMetaPage(data)?.meta;
	const facets = meta?.facets;

	const defaultColumnFilters = Object.entries(search)
		.filter(([key, value]) => !STATE_KEYS.has(key) && isActive(value))
		.map(([id, value]) => ({ id, value }));

	const dynamicFilterFields = useMemo(
		() => applyFacets(baseFilterFields, facets),
		[facets]
	);

	// Rows older than the moment live mode was switched on are dimmed, so the
	// ones streaming in read as new.
	const getRowClassName = useCallback(
		(row: { original: LogRow }) =>
			cn(
				levelRowClassName(row.original.level),
				liveMode.timestamp &&
					row.original.date.getTime() <= liveMode.timestamp &&
					"opacity-50"
			),
		[liveMode.timestamp]
	);

	return (
		<DataTableInfinite
			chartSlot={
				<TimelineChart
					className="-mb-2"
					columnId="date"
					data={meta?.chartData ?? []}
					series={CHART_SERIES}
				/>
			}
			columns={columns}
			commandSlot={
				<DataTableFilterCommand
					schema={filterSchema.definition}
					tableId={`logs:${env.slug}`}
				/>
			}
			data={flatData}
			defaultColumnFilters={defaultColumnFilters}
			defaultColumnSorting={search.sort ? [search.sort] : undefined}
			defaultColumnVisibility={defaultColumnVisibility}
			defaultRowSelection={search.uuid ? { [search.uuid]: true } : undefined}
			fetchNextPage={fetchNextPage}
			fetchPreviousPage={fetchPreviousPage}
			filterFields={dynamicFilterFields}
			filterRows={meta?.filterRowCount}
			footerSlot={<LogsFooter />}
			getFacetedMinMaxValues={getFacetedMinMaxValues(facets)}
			getFacetedUniqueValues={getFacetedUniqueValues(facets)}
			getRowClassName={getRowClassName}
			getRowId={getRowId}
			hasNextPage={hasNextPage}
			isFetching={isFetching}
			isLoading={isLoading}
			renderLiveRow={(props) => {
				if (!liveMode.timestamp) {
					return null;
				}
				if (props?.row.original.uuid !== liveMode.row?.uuid) {
					return null;
				}
				return <LiveRow>Live · new operations appear above</LiveRow>;
			}}
			sheetSlot={
				<SheetSlot
					filterRows={meta?.filterRowCount ?? 0}
					sheetFields={sheetFields}
					totalRows={meta?.totalRowCount ?? 0}
					totalRowsFetched={flatData.length}
				/>
			}
			tableId="logs"
			toolbarActions={
				<>
					<DataTableRefreshButton onClick={refresh} />
					<LiveButton fetchPreviousPage={fetchPreviousPage} />
				</>
			}
			totalRows={meta?.totalRowCount}
			totalRowsFetched={flatData.length}
		/>
	);
}

function SheetSlot({
	sheetFields: fields,
	totalRows,
	filterRows,
	totalRowsFetched,
}: {
	sheetFields: SheetField<LogRow>[];
	totalRows: number;
	filterRows: number;
	totalRowsFetched: number;
}) {
	const { table, rowSelection, isLoading, filterFields } = useDataTable<
		LogRow,
		unknown
	>();
	const [selectedKey] = Object.keys(rowSelection);
	const selected =
		isLoading && !selectedKey
			? undefined
			: table.getCoreRowModel().flatRows.find((row) => row.id === selectedKey);

	return (
		<DataTableSheetDetails
			title={selected?.original.operation}
			titleClassName="font-mono"
		>
			<MemoizedDataTableSheetContent
				data={selected?.original}
				fields={fields}
				filterFields={filterFields}
				metadata={{ filterRows, totalRows, totalRowsFetched }}
				table={table}
			/>
			{selected ? <OperationMessages id={selected.original.uuid} /> : null}
		</DataTableSheetDetails>
	);
}

const LEVEL_TEXT = {
	error: "text-destructive",
	http: "text-foreground",
	info: "text-foreground",
	warn: "text-foreground",
} as const;

/** What the operation logged, step by step: the part of a log line the
 * columns can't hold. */
function OperationMessages({ id }: { id: string }) {
	const { env } = useEnv();
	const href = useHref();
	const op = env.operations.find((o) => o.id === id);
	if (!op) {
		return null;
	}
	const messages = operationMessages(op, env);
	return (
		<section className="mt-4 grid gap-2 pb-6">
			<div className="flex items-center justify-between gap-2">
				<h3 className="text-sm font-medium">Messages</h3>
				{op.connectionId ? (
					<Link
						className="text-ds-accent text-xs hover:underline"
						href={href(`/connections/${op.connectionId}`)}
					>
						Open connection
					</Link>
				) : null}
			</div>
			<ol className="border-border overflow-hidden rounded-lg border">
				{messages.map((m) => (
					<li
						className={cn(
							"border-border text-code flex gap-3 border-b px-3 py-2 font-mono last:border-b-0",
							m.level === "warn" && "bg-warning/10",
							m.level === "error" && "bg-error/5"
						)}
						key={`${m.at}:${m.text}`}
					>
						<span className="text-muted-foreground shrink-0">
							{clock(m.at)}
						</span>
						<span className={cn("min-w-0 break-all", LEVEL_TEXT[m.level])}>
							{m.http
								? `${m.http.status} ${m.http.method} ${m.http.url} · ${m.http.ms}ms`
								: m.text}
						</span>
					</li>
				))}
			</ol>
			<p className="text-muted-foreground text-xs">
				Request and response bodies aren't logged. Authorization headers and
				credentials are redacted.
			</p>
		</section>
	);
}

/** The filter rail's footer: retention and the table's own shortcuts. */
function LogsFooter() {
	return (
		<div className="text-muted-foreground grid gap-2 text-xs">
			<p>Operations are kept for 15 days.</p>
			<div className="flex flex-wrap items-center gap-x-3 gap-y-1">
				<span className="flex items-center gap-1.5">
					<ShortcutKeys keys={["/"]} /> Filter
				</span>
				<span className="flex items-center gap-1.5">
					<ShortcutKeys id="logs:live" /> Live
				</span>
				<span className="flex items-center gap-1.5">
					<ShortcutKeys keys={["?"]} /> All shortcuts
				</span>
			</div>
		</div>
	);
}
