import type {
	ColumnDef,
	ColumnFiltersState,
	ColumnVisibilityState,
	PaginationState,
	ReactTable,
	RowData,
	RowSelectionState,
	SortingState,
	Table,
} from "@tanstack/react-table";
import { createContext, useContext, useMemo } from "react";
import { ControlsProvider } from "@/components/data-table/controls";
import type { DataTableFilterField } from "@/components/data-table/types";
import type { DataTableFeatures } from "@/lib/table/features";
import { DataTableStoreSync } from "./data-table-store-sync";

// REMINDER: read about how to move controlled state out of the useTable hook
// https://github.com/TanStack/table/discussions/4005#discussioncomment-7303569

interface DataTableStateContextType {
	columnFilters: ColumnFiltersState;
	columnOrder: string[];
	columnVisibility: ColumnVisibilityState;
	enableColumnOrdering: boolean;
	pagination: PaginationState;
	rowSelection: RowSelectionState;
	sorting: SortingState;
}

/**
 * `TFeatures` is pinned to `DataTableFeatures` rather than left generic.
 *
 * v9 declares it `in out` — invariant — so a component generic over `TFeatures`
 * cannot resolve any feature API (TypeScript cannot evaluate the feature-map
 * lookup behind an unresolved type parameter), and `Table<any, TData>` is not a
 * supertype it could fall back to. Pinning is the only typing that works, and
 * it costs nothing here: `features.ts` ships as part of the block, so a
 * consumer who registers extra features edits that one file and every type
 * below follows through `typeof dataTableFeatures`.
 */
interface DataTableBaseContextType<
	TData extends RowData = RowData,
	TValue = unknown,
> {
	columns: ColumnDef<DataTableFeatures, TData, TValue>[];
	filterFields: DataTableFilterField<TData>[];
	filterRows?: number;
	getFacetedMinMaxValues?: (
		table: Table<DataTableFeatures, TData>,
		columnId: string
	) => undefined | [number, number];
	getFacetedUniqueValues?: (
		table: Table<DataTableFeatures, TData>,
		columnId: string
	) => Map<string, number>;
	isLoading?: boolean;
	// `ReactTable`, not the core `Table`: `table.state` (v9's replacement for
	// `getState()`), `table.Subscribe` and `table.FlexRender` are added by
	// `useTable` and consumers of this context read them.
	table: ReactTable<DataTableFeatures, TData>;
	totalRows?: number;
}

interface DataTableContextType<
	TData extends RowData = RowData,
	TValue = unknown,
> extends DataTableStateContextType,
		DataTableBaseContextType<TData, TValue> {}

export const DataTableContext = createContext<DataTableContextType<
	any,
	any
> | null>(null);

export function DataTableProvider<TData extends RowData, TValue>({
	children,
	...props
}: Partial<DataTableStateContextType> &
	DataTableBaseContextType<TData, TValue> & {
		children: React.ReactNode;
	}) {
	const value = useMemo(
		// eslint-disable-next-line react-hooks/preserve-manual-memoization
		() => ({
			...props,
			columnFilters: props.columnFilters ?? [],
			columnOrder: props.columnOrder ?? [],
			columnVisibility: props.columnVisibility ?? {},
			enableColumnOrdering: props.enableColumnOrdering ?? false,
			pagination: props.pagination ?? { pageIndex: 0, pageSize: 10 },
			rowSelection: props.rowSelection ?? {},
			sorting: props.sorting ?? [],
		}),
		[
			props.columnFilters,
			props.sorting,
			props.rowSelection,
			props.columnOrder,
			props.columnVisibility,
			props.pagination,
			props.table,
			props.filterFields,
			props.columns,
			props.enableColumnOrdering,
			props.isLoading,
			props.totalRows,
			props.filterRows,
			props.getFacetedUniqueValues,
			props.getFacetedMinMaxValues,
		]
	);

	return (
		// `TData` is invariant in v9, so a concrete `DataTableContextType<TData>`
		// is not assignable to the erased `<any, any>` the context is declared
		// with — even though `any` is involved. React contexts cannot be generic,
		// so the erasure happens here and `useDataTable` casts it back.
		<DataTableContext.Provider value={value as DataTableContextType<any, any>}>
			<ControlsProvider>
				<DataTableStoreSync />
				{children}
			</ControlsProvider>
		</DataTableContext.Provider>
	);
}

export function useDataTable<TData extends RowData, TValue>() {
	const context = useContext(DataTableContext);

	if (!context) {
		throw new Error("useDataTable must be used within a DataTableProvider");
	}

	return context as DataTableContextType<TData, TValue>;
}
