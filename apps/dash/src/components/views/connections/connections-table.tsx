"use client";

import { cn } from "@securefabric/ui/lib/utils";
import {
	type ColumnFiltersState,
	type ColumnVisibilityState,
	flexRender,
	type PaginationState,
	type RowSelectionState,
	type SortingState,
	useTable,
} from "@tanstack/react-table";
import {
	ChevronLeftIcon,
	ChevronRightIcon,
	ChevronsLeftIcon,
	ChevronsRightIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/custom/table";
import { useControls } from "@/components/data-table/controls";
import { DataTableActionsBar } from "@/components/data-table/data-table-actions/bar";
import { createActionsColumn } from "@/components/data-table/data-table-actions/column";
import { DataTableActionsProvider } from "@/components/data-table/data-table-actions/provider";
import { DataTableFilterCommand } from "@/components/data-table/data-table-filter-command";
import { DataTableFilterControls } from "@/components/data-table/data-table-filter-controls";
import { DataTableFloatingBar } from "@/components/data-table/data-table-floating-bar";
import {
	DataTableProvider,
	useDataTable,
} from "@/components/data-table/data-table-provider";
import { DataTableToolbar } from "@/components/data-table/data-table-toolbar";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { getColumnVisibilityKey } from "@/lib/constants/local-storage";
import { isActive } from "@/lib/filters";
import { useFilterState } from "@/lib/store/hooks/useFilterState";
import { dataTableFeatures } from "@/lib/table/features";
import {
	generateColumns,
	generateFilterFields,
	getDefaultColumnVisibility,
} from "@/lib/table-schema";
import type { Connection } from "@/lib/types";
import {
	connectionActions,
	connectionActionsFetch,
	rowActionsFor,
} from "./actions";
import { type FilterState, filterSchema } from "./schema";
import {
	type ConnectionRow,
	tableSchema,
	toConnectionRow,
} from "./table-schema";

const PAGE_SIZES = [10, 25, 50] as const;
const NO_FILTERS: readonly string[] = [];
/** On an integration's page every row shares the tool and integration. */
export const INTEGRATION_FIXED_FILTERS: readonly string[] = [
	"provider",
	"integration",
];

const baseColumns = [
	...generateColumns<ConnectionRow>(tableSchema.definition),
	createActionsColumn<ConnectionRow>(),
];
const baseFilterFields = generateFilterFields<ConnectionRow>(
	tableSchema.definition
);
const defaultColumnVisibility = getDefaultColumnVisibility(
	tableSchema.definition
);

const getRowId = (row: ConnectionRow): string => row.id;
/** Cells that do their own thing on click instead of opening the row. */
const INTERACTIVE_CELLS = new Set(["select", "actions"]);
const FIXED_WIDTH = new Set(["select", "actions", "status", "kind", "records"]);

function sortFilters(filters: ColumnFiltersState): ColumnFiltersState {
	return [...filters].sort((a, b) => a.id.localeCompare(b.id));
}

/** The adapter's state as TanStack column filters, in a stable order. */
function filtersFromState(state: FilterState): ColumnFiltersState {
	return sortFilters(
		Object.entries(state)
			.filter(([key, value]) => key !== "sort" && isActive(value))
			.map(([id, value]) => ({ id, value }))
	);
}

/**
 * The connections list on the data-table kit, client-side: filter rail with
 * counts, the `/` filter command, column visibility, multi-select with the
 * actions block's bulk bar, a per-row action menu, and pagination.
 *
 * Filter state comes from whichever adapter the page wraps it in, so the same
 * table reads the URL on the connections page and an in-memory store inside
 * an integration's tab (see ./schema.ts).
 */
export function ConnectionsTable({
	connections,
	tableId,
	emptyState,
	omitFilters = NO_FILTERS,
}: {
	connections: Connection[];
	tableId: string;
	emptyState?: ReactNode;
	/** Facets the page has already fixed, e.g. the tool on an integration's
	 * page, where a one-option filter is noise. */
	omitFilters?: readonly string[];
}) {
	const { env } = useEnv();
	const data = useMemo(() => connections.map(toConnectionRow), [connections]);
	const actions = useMemo(() => connectionActions(env.slug), [env.slug]);
	const byId = useMemo(
		() => new Map(connections.map((c) => [c.id, c])),
		[connections]
	);
	return (
		<DataTableActionsProvider
			actions={actions}
			fetcher={connectionActionsFetch}
			getRowActions={(row: ConnectionRow) => {
				const conn = byId.get(row.id);
				return conn ? rowActionsFor(conn) : [];
			}}
			getRowId={getRowId}
			getRowLabel={(row: ConnectionRow) => row.customer}
		>
			<TableBodyWithState
				data={data}
				emptyState={emptyState}
				omitFilters={omitFilters}
				tableId={tableId}
			/>
		</DataTableActionsProvider>
	);
}

function TableBodyWithState({
	data,
	tableId,
	emptyState,
	omitFilters,
}: {
	data: ConnectionRow[];
	tableId: string;
	emptyState?: ReactNode;
	omitFilters: readonly string[];
}) {
	const search = useFilterState<FilterState>();
	const storeFilters = filtersFromState(search);
	const [columnFilters, setColumnFilters] =
		useState<ColumnFiltersState>(storeFilters);

	// Follow changes made outside the table: a sidebar view or ⌘K rewriting the
	// URL while the page is open. The table writes its own changes back to the
	// adapter (DataTableStoreSync), so those arrive here equal and are skipped.
	const storeKey = JSON.stringify(storeFilters);
	const [seenStoreKey, setSeenStoreKey] = useState(storeKey);
	if (storeKey !== seenStoreKey) {
		setSeenStoreKey(storeKey);
		if (storeKey !== JSON.stringify(sortFilters(columnFilters))) {
			setColumnFilters(storeFilters);
		}
	}
	const [sorting, setSorting] = useState<SortingState>(
		search.sort ? [search.sort] : []
	);
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
	const [pagination, setPagination] = useState<PaginationState>({
		pageIndex: 0,
		pageSize: PAGE_SIZES[0],
	});
	const [columnVisibility, setColumnVisibility] =
		useLocalStorage<ColumnVisibilityState>(
			getColumnVisibilityKey(tableId),
			defaultColumnVisibility
		);

	// A filter change can leave you on a page past the end.
	// biome-ignore lint/correctness/useExhaustiveDependencies: resets on filter change only.
	useEffect(() => {
		setPagination((p) => ({ ...p, pageIndex: 0 }));
	}, [columnFilters]);

	// The tool filter lists the tools in this table, not the whole catalog.
	const filterFields = useMemo(() => {
		const providers = [...new Set(data.map((r) => r.provider))];
		return baseFilterFields
			.filter((f) => !omitFilters.includes(String(f.value)))
			.map((f) =>
				f.value === "provider"
					? { ...f, options: providers.map((p) => ({ label: p, value: p })) }
					: f
			);
	}, [data, omitFilters]);

	// v9's useTable returns a new table whenever the options object changes
	// identity, so the options are memoized (see data-table-infinite.tsx).
	const tableOptions = useMemo(
		() => ({
			columns: baseColumns,
			data,
			enableMultiRowSelection: true,
			features: dataTableFeatures,
			getRowId,
			onColumnFiltersChange: setColumnFilters,
			onColumnVisibilityChange: setColumnVisibility,
			onPaginationChange: setPagination,
			onRowSelectionChange: setRowSelection,
			onSortingChange: setSorting,
			state: {
				columnFilters,
				columnVisibility,
				pagination,
				rowSelection,
				sorting,
			},
		}),
		[
			data,
			columnFilters,
			columnVisibility,
			pagination,
			rowSelection,
			sorting,
			setColumnVisibility,
		]
	);
	const table = useTable(tableOptions);

	return (
		<DataTableProvider
			columnFilters={columnFilters}
			columns={baseColumns}
			filterFields={filterFields}
			pagination={pagination}
			rowSelection={rowSelection}
			sorting={sorting}
			table={table}
		>
			<div className="flex w-full flex-col gap-4 sm:flex-row sm:[--controls-width:15rem]">
				<FilterPanel />
				<div className="flex min-w-0 flex-1 flex-col gap-3">
					<DataTableFilterCommand
						schema={filterSchema.definition}
						tableId={tableId}
					/>
					<DataTableToolbar />
					<Rows emptyState={emptyState} />
					<Pagination />
				</div>
			</div>
			<DataTableFloatingBar<ConnectionRow>>
				{({ rows }) => <DataTableActionsBar rows={rows} />}
			</DataTableFloatingBar>
		</DataTableProvider>
	);
}

/** Same collapse as the infinite table's: `w-0` rather than `hidden`, so it
 * can animate, with `inert` so the hidden filters can't take focus. */
function FilterPanel() {
	const { open } = useControls();
	return (
		<div
			className={cn(
				"hidden sm:block sm:w-(--controls-width) sm:shrink-0 sm:self-start",
				"sm:group-data-[expanded=false]/controls:w-0",
				"overflow-hidden transition-[width] duration-200 ease-linear motion-reduce:transition-none"
			)}
			inert={!open}
		>
			<div className="sm:w-(--controls-width)">
				<DataTableFilterControls />
			</div>
		</div>
	);
}

function Rows({ emptyState }: { emptyState?: ReactNode }) {
	const { table, columns } = useDataTable<ConnectionRow, unknown>();
	const router = useRouter();
	const href = useHref();
	const { rows } = table.getRowModel();
	return (
		<div className="border-border overflow-hidden rounded-lg border">
			<Table>
				<TableHeader className="bg-muted/50">
					{table.getHeaderGroups().map((group) => (
						<TableRow className="hover:bg-transparent" key={group.id}>
							{group.headers.map((header) => (
								<TableHead
									key={header.id}
									// Only the fixed columns get a width; the rest share what's left,
									// so Customer gets the room it needs.
									style={
										FIXED_WIDTH.has(header.column.id)
											? { width: header.column.getSize() }
											: undefined
									}
								>
									{header.isPlaceholder
										? null
										: flexRender(
												header.column.columnDef.header,
												header.getContext()
											)}
								</TableHead>
							))}
						</TableRow>
					))}
				</TableHeader>
				<TableBody>
					{rows.length ? (
						rows.map((row) => (
							<TableRow
								className="cursor-pointer"
								data-state={row.getIsSelected() ? "selected" : undefined}
								key={row.id}
								onClick={() => router.push(href(`/connections/${row.id}`))}
							>
								{row.getVisibleCells().map((cell) => (
									<TableCell
										key={cell.id}
										onClick={
											INTERACTIVE_CELLS.has(cell.column.id)
												? (e) => e.stopPropagation()
												: undefined
										}
									>
										{flexRender(cell.column.columnDef.cell, cell.getContext())}
									</TableCell>
								))}
							</TableRow>
						))
					) : (
						<TableRow className="hover:bg-transparent">
							<TableCell className="h-32 text-center" colSpan={columns.length}>
								{emptyState ?? (
									<span className="text-muted-foreground text-sm">
										No connections match these filters.
									</span>
								)}
							</TableCell>
						</TableRow>
					)}
				</TableBody>
			</Table>
		</div>
	);
}

function Pagination() {
	const { table, pagination } = useDataTable<ConnectionRow, unknown>();
	const pageCount = Math.max(1, table.getPageCount());
	const filtered = table.getFilteredRowModel().rows.length;
	const total = table.getCoreRowModel().rows.length;
	return (
		<div className="text-muted-foreground flex flex-wrap items-center justify-between gap-3 text-sm">
			<span className="tabular-nums">
				{filtered === total
					? `${total} connections`
					: `${filtered} of ${total} connections`}
			</span>
			<div className="flex items-center gap-4">
				<div className="flex items-center gap-2">
					<span className="hidden sm:inline">Rows per page</span>
					<Select
						onValueChange={(value) => table.setPageSize(Number(value))}
						value={String(pagination.pageSize)}
					>
						<SelectTrigger
							aria-label="Rows per page"
							className="w-18"
							size="sm"
						>
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							{PAGE_SIZES.map((size) => (
								<SelectItem key={size} value={String(size)}>
									{size}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</div>
				<span className="tabular-nums">
					Page {pagination.pageIndex + 1} of {pageCount}
				</span>
				<div className="flex items-center gap-1">
					<Button
						aria-label="First page"
						disabled={!table.getCanPreviousPage()}
						onClick={() => table.setPageIndex(0)}
						size="icon-sm"
						variant="outline"
					>
						<ChevronsLeftIcon />
					</Button>
					<Button
						aria-label="Previous page"
						disabled={!table.getCanPreviousPage()}
						onClick={() => table.previousPage()}
						size="icon-sm"
						variant="outline"
					>
						<ChevronLeftIcon />
					</Button>
					<Button
						aria-label="Next page"
						disabled={!table.getCanNextPage()}
						onClick={() => table.nextPage()}
						size="icon-sm"
						variant="outline"
					>
						<ChevronRightIcon />
					</Button>
					<Button
						aria-label="Last page"
						disabled={!table.getCanNextPage()}
						onClick={() => table.setPageIndex(pageCount - 1)}
						size="icon-sm"
						variant="outline"
					>
						<ChevronsRightIcon />
					</Button>
				</div>
			</div>
		</div>
	);
}
