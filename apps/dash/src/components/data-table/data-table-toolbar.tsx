"use client";

import { Button } from "@securefabric/ui/components/button";
import { Kbd } from "@securefabric/ui/primitives/kbd";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@securefabric/ui/primitives/tooltip";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useControls } from "@/components/data-table/controls";
import { useDataTable } from "@/components/data-table/data-table-provider";
import { useHotKey } from "@/hooks/use-hot-key";
import { formatCompactNumber } from "@/lib/table/format";
import { DataTableFilterControlsDrawer } from "./data-table-filter-controls-drawer";
import { DataTableResetButton } from "./data-table-reset-button";
import { DataTableViewOptions } from "./data-table-view-options";
import { TOOLTIP_DELAY } from "./ui-compat";

interface DataTableToolbarProps {
	renderActions?: () => React.ReactNode;
}

export function DataTableToolbar({ renderActions }: DataTableToolbarProps) {
	const { table, isLoading, columnFilters, totalRows, filterRows } =
		useDataTable();
	const { open, setOpen } = useControls();
	// securefabric: ⌘B toggles the app sidebar, so the filter rail takes ⌘⇧B.
	useHotKey(() => setOpen((prev) => !prev), "b", { shift: true });
	const rows = {
		filtered: filterRows ?? table.getFilteredRowModel().rows.length,
		total: totalRows ?? table.getCoreRowModel().rows.length,
	};

	return (
		<div className="flex flex-wrap items-center justify-between gap-4">
			<div className="flex flex-wrap items-center gap-2">
				<TooltipProvider {...TOOLTIP_DELAY}>
					<Tooltip>
						<TooltipTrigger
							render={
								<Button
									className="hidden gap-2 sm:flex"
									onClick={() => setOpen((prev) => !prev)}
									variant="ghost"
								/>
							}
						>
							{open ? (
								<>
									<PanelLeftClose className="h-4 w-4" />
									<span className="hidden md:block">Hide filters</span>
								</>
							) : (
								<>
									<PanelLeftOpen className="h-4 w-4" />
									<span className="hidden md:block">Show filters</span>
								</>
							)}
						</TooltipTrigger>
						<TooltipContent side="right">
							<p className="text-nowrap">
								Toggle filters with{" "}
								<Kbd className="text-muted-foreground group-hover:text-accent-foreground ml-1">
									<span className="mr-1">⌘⇧</span>
									<span>B</span>
								</Kbd>
							</p>
						</TooltipContent>
					</Tooltip>
				</TooltipProvider>
				<div className="block sm:hidden">
					<DataTableFilterControlsDrawer />
				</div>
				<div>
					<p className="text-muted-foreground hidden text-sm sm:block">
						<span className="font-mono font-medium">
							{formatCompactNumber(rows.filtered)}
						</span>{" "}
						of{" "}
						<span className="font-mono font-medium">
							{formatCompactNumber(rows.total)}
						</span>{" "}
						{rows.total === 1 ? "row" : "rows"}
					</p>
					<p className="text-muted-foreground block text-sm sm:hidden">
						<span className="font-mono font-medium">
							{formatCompactNumber(rows.filtered)}
						</span>{" "}
						{rows.filtered === 1 ? "row" : "rows"}
					</p>
				</div>
			</div>
			<div className="ml-auto flex items-center gap-2">
				{columnFilters.length ? <DataTableResetButton /> : null}
				{renderActions?.()}
				<DataTableViewOptions />
			</div>
		</div>
	);
}
