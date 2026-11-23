"use client";

import { Button } from "@securefabric/ui/components/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@securefabric/ui/primitives/dropdown-menu";
import type { ColumnDef, RowData } from "@tanstack/react-table";
import { MoreHorizontal } from "lucide-react";
import type { DataTableFeatures } from "@/lib/table/features";
import { useDataTableActions } from "./provider";
import { rowScopedActions } from "./utils";

/** The cell: a menu of the row-scoped actions this row is stamped with. */
export function DataTableActionsCell<TData>({
	row,
}: {
	row: { original: TData };
}) {
	const { actions, getRowId, getRowActions, getRowLabel, trigger, isPending } =
		useDataTableActions<TData>();
	const available = rowScopedActions(actions, getRowActions(row.original));
	if (available.length === 0) return null;
	const id = getRowId(row.original);
	// Never the row id: it is the internal key the wire uses, which for a
	// composite or opaque key reads as noise. Hosts name the row themselves.
	const label = getRowLabel?.(row.original);

	return (
		<div
			className="flex items-center justify-center"
			// The row itself opens the sheet on click and on Enter. Both bubble up
			// from the trigger — and, through React's tree, from the portalled menu
			// items — so both stop here. Only the keys that open the row are
			// stopped; everything else keeps bubbling to the row, the table, and
			// any app-level shortcut listening above them.
			onClick={(event) => event.stopPropagation()}
			onKeyDown={(event) => {
				if (event.key === "Enter" || event.key === " ") {
					event.stopPropagation();
				}
			}}
		>
			<DropdownMenu>
				{/* securefabric: base-ui `render` in place of Radix `asChild`. */}
				<DropdownMenuTrigger
					render={
						<Button
							aria-label={label ? `Actions for ${label}` : "Row actions"}
							className="size-5"
							size="icon-xs"
							variant="ghost"
						/>
					}
				>
					<MoreHorizontal />
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end">
					{available.map((action) => (
						<DropdownMenuItem
							// One action at a time, as in the bulk bar: a second trigger
							// while one is on the wire races the first for the shared
							// confirmation dialog.
							disabled={isPending}
							key={action.id}
							onSelect={() =>
								trigger(action, { ids: [id], scope: "ids" }, { count: 1 })
							}
							variant={
								action.variant === "destructive" ? "destructive" : "default"
							}
						>
							{action.label}
						</DropdownMenuItem>
					))}
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}

/**
 * A column that renders `DataTableActionsCell`. Append it to the generated
 * columns; it needs a `DataTableActionsProvider` above the table. The column
 * is hideable — pair it with a `columnVisibility` default of `{ [id]: false }`
 * to keep it hidden until enabled from the view options.
 */
export function createActionsColumn<TData extends RowData>(
	options: { id?: string; size?: number } = {}
): ColumnDef<DataTableFeatures, TData> {
	const { id = "actions", size = 40 } = options;
	return {
		cell: ({ row }) => <DataTableActionsCell row={row} />,
		enableHiding: true,
		enableResizing: false,
		enableSorting: false,
		header: () => <span className="sr-only">Actions</span>,
		id,
		maxSize: size,
		meta: { kind: "actions", label: "Actions" },
		minSize: size,
		size,
	};
}
