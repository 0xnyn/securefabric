"use client";

import { type schemas, unwrap } from "@securefabric/client";
import { Badge, type Tone } from "@securefabric/ui/components/badge";
import { Button } from "@securefabric/ui/components/button";
import { duration } from "@securefabric/ui/lib/format";
import { cn } from "@securefabric/ui/lib/utils";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { FilterIcon } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";
import { DataTableFilterCommand } from "@/components/data-table/data-table-filter-command";
import { DataTableInfinite } from "@/components/data-table/data-table-infinite";
import { HoverCardTimestamp } from "@/components/data-table/data-table-infinite/hover-card-timestamp";
import { useDataTable } from "@/components/data-table/data-table-provider";
import { DataTableSheetDetails } from "@/components/data-table/data-table-sheet/data-table-sheet-details";
import type { DataTableFilterField } from "@/components/data-table/types";
import { ConnectorLogo } from "@/components/domain/connector-logo";
import { JsonBlock } from "@/components/domain/json-block";
import { QueryState } from "@/components/domain/query-state";
import { useEnv, useHref } from "@/components/shell/env-context";
import { humanize, syncActionLabel } from "@/lib/labels";
import { useNuqsAdapter } from "@/lib/store/adapters/nuqs";
import { useFilterActions } from "@/lib/store/hooks/useFilterActions";
import { useFilterState } from "@/lib/store/hooks/useFilterState";
import { DataTableStoreProvider } from "@/lib/store/provider/DataTableStoreProvider";
import { field } from "@/lib/store/schema";
import type { DataTableFeatures } from "@/lib/table/features";
import { OP_TONES } from "@/lib/types";
import { LogLines } from "./connection";

/*
 * The operation log (OBS-01/02): one row per sync, credential check, webhook
 * in or out, passthrough call or write-back action. Same viewer as the audit
 * log: filters in a rail, a filter command, scroll to load older pages
 * (keyset cursors, so a page costs the same however far back you go), and a
 * details sheet with the operation's request log, ↑/↓ between rows.
 */

type Operation = schemas["OperationOut"];
type OperationPage = schemas["Page_OperationOut_"];

interface OperationRow extends Omit<Operation, "started_at"> {
	started_at: Date;
}

const TABLE_ID = "logs";
const PAGE_SIZE = 100;

export const KIND_LABELS: Record<string, string> = {
	action: "Write-back action",
	auth: "Credential check",
	passthrough: "Passthrough call",
	sync: "Sync",
	webhook_in: "Webhook received",
	webhook_out: "Webhook sent",
};

const STATUS_LABELS: Record<string, string> = {
	cancelled: "Cancelled",
	failed: "Failed",
	running: "Running",
	success: "Succeeded",
	warning: "Finished with warnings",
};

const STATUS_DOT: Record<Tone, string> = {
	accent: "bg-ds-accent",
	busy: "bg-ds-accent",
	error: "bg-destructive",
	neutral: "bg-muted-foreground/50",
	ok: "bg-ds-success",
	warn: "bg-ds-severity-medium",
};

/** What an operation did, in words: sync actions are `stream:mode`. */
function actionLabel(kind: string, action: string): string {
	return kind === "sync" ? syncActionLabel(action) : humanize(action);
}

const filterSchema = {
	connection_id: field.string(),
	kind: field.array(field.string()).delimiter(","),
	sort: field.sort(),
	started_at: field.array(field.timestamp()).delimiter("-"),
	status: field.array(field.string()).delimiter(","),
	uuid: field.string(),
};

interface FilterState {
	connection_id: string | null;
	kind: string[];
	started_at: Date[];
	status: string[];
}

const FILTER_FIELDS: DataTableFilterField<OperationRow>[] = [
	{
		commandDisabled: true,
		defaultOpen: true,
		label: "Started",
		type: "timerange",
		value: "started_at",
	},
	{
		defaultOpen: true,
		label: "Status",
		options: Object.entries(STATUS_LABELS).map(([value, label]) => ({
			label,
			value,
		})),
		type: "checkbox",
		value: "status",
	},
	{
		defaultOpen: true,
		label: "Type",
		options: Object.entries(KIND_LABELS).map(([value, label]) => ({
			label,
			value,
		})),
		type: "checkbox",
		value: "kind",
	},
	{ label: "Connection ID", type: "input", value: "connection_id" },
];

function useColumns(): ColumnDef<DataTableFeatures, OperationRow>[] {
	return useMemo(
		() => [
			{
				accessorKey: "status",
				cell: ({ row }) => {
					const tone = OP_TONES[row.original.status] ?? "neutral";
					return (
						<span className="flex items-center gap-2">
							<span
								className={cn("size-2 shrink-0 rounded-full", STATUS_DOT[tone])}
							/>
							<span className="truncate">
								{STATUS_LABELS[row.original.status] ??
									humanize(row.original.status)}
							</span>
						</span>
					);
				},
				filterFn: "arrSome",
				header: "Status",
				meta: { label: "Status" },
				size: 150,
			},
			{
				accessorKey: "started_at",
				cell: ({ row }) => (
					<HoverCardTimestamp date={row.original.started_at} />
				),
				enableResizing: false,
				filterFn: "inDateRange",
				header: "Started",
				meta: { cellClassName: "font-mono", label: "Started" },
				minSize: 190,
				size: 190,
			},
			{
				accessorKey: "kind",
				cell: ({ row }) =>
					KIND_LABELS[row.original.kind] ?? humanize(row.original.kind),
				filterFn: "arrSome",
				header: "Type",
				meta: { label: "Type" },
				size: 170,
			},
			{
				accessorKey: "action",
				cell: ({ row }) => (
					<span className="truncate">
						{actionLabel(row.original.kind, row.original.action)}
					</span>
				),
				header: "What",
				meta: { label: "What" },
				size: 220,
			},
			{
				accessorKey: "vendor",
				cell: ({ row }) =>
					row.original.vendor ? (
						<span className="flex min-w-0 items-center gap-2">
							<ConnectorLogo id={row.original.vendor} size={18} />
							<span className="truncate">
								{humanize(row.original.vendor.toLowerCase())}
							</span>
						</span>
					) : (
						<span className="text-muted-foreground">—</span>
					),
				header: "Tool",
				meta: { label: "Tool" },
				size: 170,
			},
			{
				accessorKey: "duration_ms",
				cell: ({ row }) =>
					row.original.duration_ms === null ? (
						<span className="text-muted-foreground">—</span>
					) : (
						<span className="tabular-nums">
							{duration(row.original.duration_ms)}
						</span>
					),
				header: "Took",
				meta: {
					cellClassName: "text-right",
					headerClassName: "text-right",
					label: "Took",
				},
				size: 100,
			},
			{
				accessorKey: "line_count",
				cell: ({ row }) => (
					<span className="text-muted-foreground tabular-nums">
						{row.original.line_count}
					</span>
				),
				header: "Lines",
				meta: {
					cellClassName: "text-right",
					headerClassName: "text-right",
					label: "Lines",
				},
				size: 80,
			},
			{
				accessorKey: "connection_id",
				cell: ({ row }) => (
					<span className="font-mono text-xs">
						{row.original.connection_id ?? "—"}
					</span>
				),
				filterFn: "includesString",
				header: "Connection ID",
				meta: { label: "Connection ID" },
				size: 300,
			},
		],
		[]
	);
}

export function LogsView() {
	const adapter = useNuqsAdapter(filterSchema, { id: TABLE_ID });
	return (
		<div className="flex h-full flex-col">
			<div className="border-border border-b px-4 py-4 sm:px-6">
				<h1 className="text-base font-semibold">Logs</h1>
				<p className="text-muted-foreground text-xs">
					What ran, when and how it went. Kept for 30 days.
				</p>
			</div>
			<div className="min-h-0 flex-1">
				<DataTableStoreProvider adapter={adapter}>
					<LogsTable />
				</DataTableStoreProvider>
			</div>
		</div>
	);
}

function LogsTable() {
	const { client, env } = useEnv();
	const state = useFilterState<FilterState & Record<string, unknown>>();
	const columns = useColumns();
	const since = state.started_at?.[0];
	const query = {
		connectionId: state.connection_id ?? undefined,
		kind: state.kind?.length ? state.kind.join(",") : undefined,
		since: since ? since.toISOString() : undefined,
		status: state.status?.length ? state.status.join(",") : undefined,
	};
	const list = useInfiniteQuery({
		getNextPageParam: (last: OperationPage) => last.next_cursor ?? undefined,
		initialPageParam: undefined as string | undefined,
		placeholderData: (prev) => prev,
		queryFn: ({ pageParam }): Promise<OperationPage> =>
			unwrap(
				client.GET("/v1/operations", {
					params: { query: { ...query, cursor: pageParam, limit: PAGE_SIZE } },
				})
			),
		queryKey: ["operations", env.id, query],
		refetchInterval: 15_000,
	});
	const rows = useMemo<OperationRow[]>(
		() =>
			(list.data?.pages ?? []).flatMap((p) =>
				p.items.map((o) => ({ ...o, started_at: new Date(o.started_at) }))
			),
		[list.data]
	);
	const facets = useMemo(() => {
		const count = (key: "kind" | "status") => {
			const m = new Map<string, number>();
			for (const r of rows) {
				m.set(r[key], (m.get(r[key]) ?? 0) + 1);
			}
			return m;
		};
		return { kind: count("kind"), status: count("status") } as Record<
			string,
			Map<string, number>
		>;
	}, [rows]);
	return (
		<DataTableInfinite
			columns={columns}
			commandSlot={
				<DataTableFilterCommand schema={filterSchema} tableId={TABLE_ID} />
			}
			data={rows}
			defaultColumnVisibility={{ connection_id: false }}
			emptyState={{
				description: "Syncs, webhooks and actions show up here as they run.",
				title: "No activity yet",
			}}
			fetchNextPage={list.fetchNextPage}
			filterFields={FILTER_FIELDS}
			footerSlot={
				<p className="text-muted-foreground text-xs">
					Counts cover loaded rows only.
				</p>
			}
			getFacetedUniqueValues={(_, columnId) => facets[columnId] ?? new Map()}
			getRowId={(r) => r.id}
			hasNextPage={list.hasNextPage}
			isFetching={list.isFetching}
			isLoading={list.isPending}
			sheetSlot={<OperationSheet />}
			tableId={TABLE_ID}
			totalRowsFetched={rows.length}
		/>
	);
}

function OperationSheet() {
	const { table, rowSelection } = useDataTable<OperationRow, unknown>();
	const { setFilters } = useFilterActions();
	const [key] = Object.keys(rowSelection);
	const row = key
		? table.getCoreRowModel().flatRows.find((r) => r.id === key)?.original
		: undefined;
	const tone = row ? (OP_TONES[row.status] ?? "neutral") : "neutral";
	return (
		<DataTableSheetDetails title={row ? actionLabel(row.kind, row.action) : ""}>
			{row ? (
				<div className="grid gap-6 p-4 text-sm">
					<div className="flex flex-wrap items-center gap-2">
						<Badge tone={tone}>
							{STATUS_LABELS[row.status] ?? humanize(row.status)}
						</Badge>
						<span className="text-muted-foreground text-xs">
							{row.duration_ms === null
								? ""
								: `Took ${duration(row.duration_ms)} · `}
							{row.line_count} {row.line_count === 1 ? "line" : "lines"}
						</span>
					</div>
					<OperationFacts row={row} />
					{Object.keys(row.summary ?? {}).length ? (
						<div className="grid gap-2">
							<span className="text-muted-foreground text-xs">Summary</span>
							<SummaryStats summary={row.summary} />
						</div>
					) : null}
					<RequestLog id={row.id} />
					{row.connection_id ? (
						<div>
							<Button
								onClick={() => {
									table.resetRowSelection();
									table
										.getColumn("connection_id")
										?.setFilterValue(row.connection_id);
									setFilters({ connection_id: row.connection_id });
								}}
								size="sm"
							>
								<FilterIcon /> Show only this connection
							</Button>
						</div>
					) : null}
				</div>
			) : null}
		</DataTableSheetDetails>
	);
}

function OperationFacts({ row }: { row: OperationRow }) {
	const href = useHref();
	return (
		<dl className="grid grid-cols-[7rem_1fr] gap-x-4 gap-y-2.5">
			<dt className="text-muted-foreground">Started</dt>
			<dd>{row.started_at.toLocaleString()}</dd>
			{row.vendor ? (
				<>
					<dt className="text-muted-foreground">Tool</dt>
					<dd className="flex items-center gap-2">
						<ConnectorLogo id={row.vendor} size={18} />
						{humanize(row.vendor.toLowerCase())}
					</dd>
				</>
			) : null}
			{row.connection_id ? (
				<>
					<dt className="text-muted-foreground">Connection</dt>
					<dd>
						<Link
							className="font-mono text-xs hover:underline"
							href={href(`/connections/${row.connection_id}`)}
						>
							{row.connection_id}
						</Link>
					</dd>
				</>
			) : null}
			{row.job_id ? (
				<>
					<dt className="text-muted-foreground">Job</dt>
					<dd>
						<Link
							className="font-mono text-xs hover:underline"
							href={href(`/jobs/${row.job_id}`)}
						>
							{row.job_id}
						</Link>
					</dd>
				</>
			) : null}
			<dt className="text-muted-foreground">Request ID</dt>
			<dd className="font-mono text-xs break-all">{row.request_id ?? "—"}</dd>
		</dl>
	);
}

function RequestLog({ id }: { id: string }) {
	const { client, env } = useEnv();
	const detail = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/operations/{operation_id}", {
					params: { path: { operation_id: id } },
				})
			),
		queryKey: ["operation", env.id, id],
	});
	return (
		<div className="grid gap-2">
			<span className="text-muted-foreground text-xs">Request log</span>
			<QueryState query={detail} rows={3}>
				{detail.data?.lines.length ? (
					<LogLines
						lines={detail.data.lines.map((l) => ({ ...l, stream: null }))}
					/>
				) : (
					<p className="text-muted-foreground text-sm">
						Nothing was logged for this run.
					</p>
				)}
			</QueryState>
		</div>
	);
}

/** Numbers as a stat grid (records added, updated…); anything else as JSON. */
function SummaryStats({ summary }: { summary: Record<string, unknown> }) {
	const numbers = Object.entries(summary).filter(
		(e): e is [string, number] => typeof e[1] === "number"
	);
	const rest = Object.fromEntries(
		Object.entries(summary).filter(
			([, v]) => typeof v !== "number" && v !== null
		)
	);
	return (
		<div className="grid gap-3">
			{numbers.length ? (
				<dl className="border-border grid grid-cols-3 divide-x divide-y overflow-hidden rounded-md border">
					{numbers.map(([k, v]) => (
						<div className="grid gap-0.5 px-3 py-2" key={k}>
							<dt className="text-muted-foreground text-xs">{humanize(k)}</dt>
							<dd className="font-medium tabular-nums">{v.toLocaleString()}</dd>
						</div>
					))}
				</dl>
			) : null}
			{Object.keys(rest).length ? <JsonBlock value={rest} /> : null}
		</div>
	);
}
