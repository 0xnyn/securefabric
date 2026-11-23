"use client";

import type { schemas } from "@securefabric/client";
import { unwrap } from "@securefabric/client";
import { Button } from "@securefabric/ui/components/button";
import { cn } from "@securefabric/ui/lib/utils";
import { PersonAvatar } from "@securefabric/ui/patterns/avatar";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import {
	BotIcon,
	FilterIcon,
	KeyRoundIcon,
	LifeBuoyIcon,
	LinkIcon,
	type LucideIcon,
} from "lucide-react";
import { lazy, Suspense, useMemo } from "react";
import { DataTableFilterCommand } from "@/components/data-table/data-table-filter-command";
import { DataTableInfinite } from "@/components/data-table/data-table-infinite";
import { HoverCardTimestamp } from "@/components/data-table/data-table-infinite/hover-card-timestamp";
import { useDataTable } from "@/components/data-table/data-table-provider";
import { DataTableSheetDetails } from "@/components/data-table/data-table-sheet/data-table-sheet-details";
import type { DataTableFilterField } from "@/components/data-table/types";
import { JsonBlock } from "@/components/domain/json-block";
import { useAccess, useEnv } from "@/components/shell/env-context";
import { useNuqsAdapter } from "@/lib/store/adapters/nuqs";
import { useFilterActions } from "@/lib/store/hooks/useFilterActions";
import { useFilterState } from "@/lib/store/hooks/useFilterState";
import { DataTableStoreProvider } from "@/lib/store/provider/DataTableStoreProvider";
import { field } from "@/lib/store/schema";
import type { DataTableFeatures } from "@/lib/table/features";

/*
 * The audit log (SEC-08) on the shared log viewer: filters in a rail, a filter
 * command, a details sheet with ↑/↓ between rows, and cursor paging as you
 * scroll. Filtering, facets and counts happen in the API (GET
 * /v1/audit_events and /facets), so the page costs the same at ten events or
 * ten million: it only ever holds the pages you've scrolled through.
 */

type AuditEvent = schemas["AuditEventOut"];
type Facets = schemas["AuditFacets"];
type AuditPage = schemas["Page_AuditEventOut_"];

/** A row as the table sees it: `at` as a Date for the time-range filter. */
interface AuditRow extends Omit<AuditEvent, "at"> {
	actor: string;
	at: Date;
}

const TABLE_ID = "audit";
const PAGE_SIZE = 100;

const filterSchema = {
	action: field.array(field.string()).delimiter(","),
	actor: field.string(),
	actor_kind: field.array(field.string()).delimiter(","),
	at: field.array(field.timestamp()).delimiter("-"),
	sort: field.sort(),
	target_id: field.string(),
	target_kind: field.array(field.string()).delimiter(","),
	uuid: field.string(),
};

interface FilterState {
	action: string[];
	actor: string | null;
	actor_kind: string[];
	at: Date[];
	target_id: string | null;
	target_kind: string[];
	uuid: string | null;
}

const ACTOR_KINDS: Record<string, string> = {
	api_key: "API key",
	connect_session: "Connect page",
	support: "SecureFabric support",
	system: "SecureFabric",
	user: "Person",
};

/** "member.role_changed" → "Member role changed". */
export function humanizeAction(action: string): string {
	const words = action.replaceAll(".", " ").replaceAll("_", " ").trim();
	return words.charAt(0).toUpperCase() + words.slice(1);
}

function humanizeKind(kind: string | null | undefined): string {
	if (!kind) {
		return "—";
	}
	const words = kind.replaceAll("_", " ");
	return words.charAt(0).toUpperCase() + words.slice(1);
}

/** The API query for a filter state. Shared by the list and the facets. */
function toQuery(state: FilterState) {
	const [from, to] = state.at;
	const csv = (v: string[] | undefined) =>
		v?.length ? v.join(",") : undefined;
	return {
		action: csv(state.action),
		actorId: state.actor ?? undefined,
		actorKind: csv(state.actor_kind),
		since: from ? from.toISOString() : undefined,
		targetId: state.target_id ?? undefined,
		targetKind: csv(state.target_kind),
		until: to ? to.toISOString() : undefined,
	};
}

// ---------------------------------------------------------------------------
// Who did it

interface ActorInfo {
	detail: string;
	kind: string;
	name: string;
}

function useActors() {
	const { client, env } = useEnv();
	const access = useAccess();
	const members = useQuery({
		queryFn: () => unwrap(client.GET("/v1/members")),
		queryKey: ["members"],
		staleTime: 60_000,
	});
	const keys = useQuery({
		enabled: access.can("keys:manage"),
		queryFn: () => unwrap(client.GET("/v1/api_keys")),
		queryKey: ["api-keys", env.id],
		staleTime: 60_000,
	});
	return useMemo(() => {
		const people = new Map(
			(members.data ?? []).map((m) => [m.user_id, m] as const)
		);
		const apiKeys = new Map((keys.data ?? []).map((k) => [k.id, k] as const));
		return (kind: string, id: string | null | undefined): ActorInfo => {
			if (kind === "user" && id) {
				const m = people.get(id);
				return {
					detail: m?.email ?? id,
					kind,
					name: m?.name ?? m?.email ?? "Former member",
				};
			}
			if (kind === "api_key" && id) {
				const k = apiKeys.get(id);
				return {
					detail: k ? `${k.prefix}…` : id,
					kind,
					name: k ? `API key “${k.name}”` : "API key",
				};
			}
			return { detail: id ?? "", kind, name: ACTOR_KINDS[kind] ?? kind };
		};
	}, [members.data, keys.data]);
}

const ACTOR_ICONS: Record<string, LucideIcon> = {
	api_key: KeyRoundIcon,
	connect_session: LinkIcon,
	support: LifeBuoyIcon,
};

function ActorAvatar({
	kind,
	seed,
	size = 20,
}: {
	kind: string;
	seed: string;
	size?: number;
}) {
	if (kind === "user") {
		return <PersonAvatar seed={seed} size={size} />;
	}
	// Not a person, so no generated face: an icon for what it is, on the same
	// square tile as organizations and accounts.
	const Icon = ACTOR_ICONS[kind] ?? BotIcon;
	return (
		<span
			aria-hidden="true"
			className={cn(
				"border-border bg-muted text-muted-foreground inline-flex shrink-0 items-center justify-center border",
				size >= 32 ? "rounded-lg" : "rounded-md"
			)}
			style={{ height: size, width: size }}
		>
			<Icon className={size >= 32 ? "size-4" : "size-3"} />
		</span>
	);
}

// ---------------------------------------------------------------------------
// Columns and filters

function useColumns(
	resolve: ReturnType<typeof useActors>
): ColumnDef<DataTableFeatures, AuditRow>[] {
	return useMemo(
		() => [
			{
				accessorKey: "at",
				cell: ({ row }) => <HoverCardTimestamp date={row.original.at} />,
				enableResizing: false,
				filterFn: "inDateRange",
				header: "Time",
				meta: { cellClassName: "font-mono", label: "Time" },
				minSize: 190,
				size: 190,
			},
			{
				accessorKey: "actor",
				cell: ({ row }) => {
					const a = resolve(row.original.actor_kind, row.original.actor_id);
					return (
						<span className="flex min-w-0 items-center gap-2">
							<ActorAvatar
								kind={row.original.actor_kind}
								seed={a.detail || a.name}
							/>
							<span className="truncate">{a.name}</span>
						</span>
					);
				},
				filterFn: "includesString",
				header: "Who",
				meta: { label: "Who" },
				size: 240,
			},
			{
				accessorKey: "action",
				cell: ({ row }) => (
					<span className="truncate">
						{humanizeAction(row.original.action)}
					</span>
				),
				filterFn: "arrSome",
				header: "What happened",
				meta: { label: "What happened" },
				size: 240,
			},
			{
				accessorKey: "target_kind",
				cell: ({ row }) => (
					<span className="flex min-w-0 items-center gap-2">
						<span className="text-muted-foreground shrink-0">
							{humanizeKind(row.original.target_kind)}
						</span>
						{row.original.target_id ? (
							<span className="truncate font-mono text-xs">
								{row.original.target_id}
							</span>
						) : null}
					</span>
				),
				filterFn: "arrSome",
				header: "On",
				meta: { label: "On" },
				size: 300,
			},
			{
				accessorKey: "actor_kind",
				cell: ({ row }) =>
					ACTOR_KINDS[row.original.actor_kind] ?? row.original.actor_kind,
				filterFn: "arrSome",
				header: "Actor type",
				meta: { label: "Actor type" },
				size: 150,
			},
			{
				accessorKey: "target_id",
				cell: ({ row }) => (
					<span className="font-mono text-xs">
						{row.original.target_id ?? "—"}
					</span>
				),
				filterFn: "includesString",
				header: "Target ID",
				meta: { label: "Target ID" },
				size: 220,
			},
			{
				accessorKey: "ip",
				cell: ({ row }) => (
					<span className="font-mono text-xs">{row.original.ip ?? "—"}</span>
				),
				header: "IP address",
				meta: { label: "IP address" },
				size: 140,
			},
		],
		[resolve]
	);
}

const DEFAULT_VISIBILITY = { actor_kind: false, ip: false, target_id: false };

function filterFields(
	facets: Facets | undefined
): DataTableFilterField<AuditRow>[] {
	const opts = (
		rows: { value: string }[] | undefined,
		label: (v: string) => string = humanizeKind
	) => (rows ?? []).map((r) => ({ label: label(r.value), value: r.value }));
	return [
		{
			commandDisabled: true,
			defaultOpen: true,
			label: "Time",
			type: "timerange",
			value: "at",
		},
		{
			defaultOpen: true,
			label: "What happened",
			options: opts(facets?.action, humanizeAction),
			type: "checkbox",
			value: "action",
		},
		{
			defaultOpen: true,
			label: "Actor type",
			options: opts(facets?.actor_kind, (v) => ACTOR_KINDS[v] ?? v),
			type: "checkbox",
			value: "actor_kind",
		},
		{
			label: "On",
			options: opts(facets?.target_kind),
			type: "checkbox",
			value: "target_kind",
		},
		{ label: "Target ID", type: "input", value: "target_id" },
	];
}

// ---------------------------------------------------------------------------
// The view

export function AuditLog() {
	const adapter = useNuqsAdapter(filterSchema, { id: TABLE_ID });
	return (
		<DataTableStoreProvider adapter={adapter}>
			<AuditTable />
		</DataTableStoreProvider>
	);
}

function AuditTable() {
	const { client, env } = useEnv();
	const state = useFilterState<FilterState & Record<string, unknown>>();
	const query = toQuery(state);
	const resolve = useActors();
	const columns = useColumns(resolve);

	const facets = useQuery({
		placeholderData: (prev) => prev,
		queryFn: () =>
			unwrap(client.GET("/v1/audit_events/facets", { params: { query } })),
		queryKey: ["audit-facets", env.id, query],
	});
	const list = useInfiniteQuery({
		getNextPageParam: (last: AuditPage) => last.next_cursor ?? undefined,
		initialPageParam: undefined as string | undefined,
		placeholderData: (prev) => prev,
		queryFn: ({ pageParam }): Promise<AuditPage> =>
			unwrap(
				client.GET("/v1/audit_events", {
					params: { query: { ...query, cursor: pageParam, limit: PAGE_SIZE } },
				})
			),
		queryKey: ["audit", env.id, query],
	});

	const rows = useMemo<AuditRow[]>(
		() =>
			(list.data?.pages ?? []).flatMap((p) =>
				p.items.map((e) => ({
					...e,
					actor: e.actor_id ?? "",
					at: new Date(e.at),
				}))
			),
		[list.data]
	);
	const facetMaps = useMemo(() => {
		const toMap = (r: { value: string; count: number }[] | undefined) =>
			new Map((r ?? []).map((x) => [x.value, x.count] as const));
		return {
			action: toMap(facets.data?.action),
			actor: toMap(facets.data?.actor_id),
			actor_kind: toMap(facets.data?.actor_kind),
			target_kind: toMap(facets.data?.target_kind),
		} as Record<string, Map<string, number>>;
	}, [facets.data]);
	const chartData = useMemo(
		() =>
			(facets.data?.histogram ?? []).map((b) => ({
				events: b.count,
				timestamp: new Date(b.at).getTime(),
			})),
		[facets.data]
	);
	const fields = useMemo(() => filterFields(facets.data), [facets.data]);

	return (
		<DataTableInfinite
			chartSlot={chartData.length ? <AuditChart data={chartData} /> : null}
			columns={columns}
			commandSlot={
				<DataTableFilterCommand schema={filterSchema} tableId={TABLE_ID} />
			}
			data={rows}
			defaultColumnVisibility={DEFAULT_VISIBILITY}
			emptyState={{
				description: "Each change shows up here with who made it.",
				title: "No changes yet",
			}}
			fetchNextPage={list.fetchNextPage}
			filterFields={fields}
			filterRows={facets.data?.total}
			footerSlot={
				<p className="text-muted-foreground text-xs">
					Kept for at least a year. Shows the last 90 days by default.
				</p>
			}
			getFacetedUniqueValues={(_, columnId) => facetMaps[columnId] ?? new Map()}
			getRowId={(r) => r.id}
			hasNextPage={list.hasNextPage}
			isFetching={list.isFetching}
			isLoading={list.isPending}
			sheetSlot={<AuditSheet resolve={resolve} />}
			tableId={TABLE_ID}
			totalRows={facets.data?.total}
			totalRowsFetched={rows.length}
		/>
	);
}

const LazyTimeline = lazy(() =>
	import("@/components/data-table/data-table-chart/timeline-chart").then(
		(m) => ({
			default: m.TimelineChart,
		})
	)
);

function AuditChart({
	data,
}: {
	data: { events: number; timestamp: number }[];
}) {
	return (
		<Suspense fallback={<div className="h-[60px]" />}>
			<LazyTimeline
				className="-mb-2"
				columnId="at"
				data={data}
				series={[{ color: "var(--ds-accent)", key: "events", label: "Events" }]}
			/>
		</Suspense>
	);
}

function AuditSheet({ resolve }: { resolve: ReturnType<typeof useActors> }) {
	const { table, rowSelection } = useDataTable<AuditRow, unknown>();
	const { setFilters } = useFilterActions();
	const [key] = Object.keys(rowSelection);
	const row = key
		? table.getCoreRowModel().flatRows.find((r) => r.id === key)?.original
		: undefined;
	const actor = row ? resolve(row.actor_kind, row.actor_id) : null;
	const only = (filters: Record<string, unknown>) => {
		table.resetRowSelection();
		for (const [id, value] of Object.entries(filters)) {
			table.getColumn(id)?.setFilterValue(value);
		}
		setFilters(filters);
	};
	return (
		<DataTableSheetDetails title={row ? humanizeAction(row.action) : ""}>
			{row && actor ? (
				<div className="grid gap-6 p-4 text-sm">
					<div className="flex items-center gap-3">
						<ActorAvatar
							kind={row.actor_kind}
							seed={actor.detail || actor.name}
							size={36}
						/>
						<div className="grid min-w-0">
							<span className="truncate font-medium">{actor.name}</span>
							<span className="text-muted-foreground truncate text-xs">
								{actor.detail}
							</span>
						</div>
					</div>
					<dl className="grid grid-cols-[7rem_1fr] gap-x-4 gap-y-2.5">
						<dt className="text-muted-foreground">When</dt>
						<dd>{row.at.toLocaleString()}</dd>
						<dt className="text-muted-foreground">Action</dt>
						<dd className="font-mono text-xs">{row.action}</dd>
						<dt className="text-muted-foreground">On</dt>
						<dd>
							{humanizeKind(row.target_kind)}{" "}
							<span className="font-mono text-xs break-all">
								{row.target_id}
							</span>
						</dd>
						<dt className="text-muted-foreground">IP address</dt>
						<dd className="font-mono text-xs">{row.ip ?? "—"}</dd>
						<dt className="text-muted-foreground">Browser</dt>
						<dd className="text-xs break-words">{row.user_agent ?? "—"}</dd>
						<dt className="text-muted-foreground">Request ID</dt>
						<dd className="font-mono text-xs break-all">
							{row.request_id ?? "—"}
						</dd>
					</dl>
					{Object.keys(row.detail ?? {}).length ? (
						<div className="grid gap-2">
							<span className="text-muted-foreground text-xs">Details</span>
							<JsonBlock value={row.detail} />
						</div>
					) : null}
					<div className="flex flex-wrap gap-2">
						{row.actor_id ? (
							<Button onClick={() => only({ actor: row.actor_id })} size="sm">
								<FilterIcon /> Show only this actor
							</Button>
						) : null}
						{row.target_id ? (
							<Button
								onClick={() => only({ target_id: row.target_id })}
								size="sm"
							>
								<FilterIcon /> Show only this{" "}
								{humanizeKind(row.target_kind).toLowerCase()}
							</Button>
						) : null}
					</div>
				</div>
			) : null}
		</DataTableSheetDetails>
	);
}
