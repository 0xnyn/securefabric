"use client";

import { Button } from "@securefabric/ui/components/button";
import { Kbd } from "@securefabric/ui/primitives/kbd";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@securefabric/ui/primitives/tooltip";
import { X } from "lucide-react";
import { useDataTable } from "@/components/data-table/data-table-provider";
import { useHotKey } from "@/hooks/use-hot-key";
import { TOOLTIP_DELAY } from "./ui-compat";

export function DataTableResetButton() {
	const { table } = useDataTable();
	useHotKey(table.resetColumnFilters, "Escape");

	return (
		<TooltipProvider {...TOOLTIP_DELAY}>
			<Tooltip>
				<TooltipTrigger
					render={
						<Button
							onClick={() => table.resetColumnFilters()}
							variant="ghost"
						/>
					}
				>
					<X className="mr-2 h-4 w-4" />
					Clear
				</TooltipTrigger>
				<TooltipContent side="left">
					<p className="text-nowrap">
						Clear filters with{" "}
						<Kbd className="text-muted-foreground group-hover:text-accent-foreground ml-1">
							<span className="mr-1">⌘</span>
							<span>Esc</span>
						</Kbd>
					</p>
				</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
}
