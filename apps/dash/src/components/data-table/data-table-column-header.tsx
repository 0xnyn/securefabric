import { Button } from "@securefabric/ui/components/button";
import { cn } from "@securefabric/ui/lib/utils";
import type { Column, RowData } from "@tanstack/react-table";
import { ChevronDown, ChevronUp } from "lucide-react";
import type React from "react";
import type { DataTableFeatures } from "@/lib/table/features";

interface DataTableColumnHeaderProps<TData extends RowData, TValue>
	extends React.ComponentProps<typeof Button> {
	column: Column<DataTableFeatures, TData, TValue>;
	title: string;
}

export function DataTableColumnHeader<TData extends RowData, TValue>({
	column,
	title,
	className,
	...props
}: DataTableColumnHeaderProps<TData, TValue>) {
	if (!column.getCanSort()) {
		return <div className={cn(className)}>{title}</div>;
	}

	return (
		<Button
			className={cn(
				"flex h-7 w-full items-center justify-between gap-2 px-0 py-0 hover:bg-transparent",
				className
			)}
			onClick={() => {
				column.toggleSorting(undefined);
			}}
			variant="ghost"
			{...props}
		>
			<span>{title}</span>
			<span className="flex flex-col">
				<ChevronUp
					className={cn(
						"-mb-0.5 size-3",
						column.getIsSorted() === "asc"
							? "text-accent-foreground"
							: "text-muted-foreground"
					)}
				/>
				<ChevronDown
					className={cn(
						"-mt-0.5 size-3",
						column.getIsSorted() === "desc"
							? "text-accent-foreground"
							: "text-muted-foreground"
					)}
				/>
			</span>
		</Button>
	);
}
