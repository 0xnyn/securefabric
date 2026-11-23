"use client";

import { cn } from "@securefabric/ui/lib/utils";
import { Check, GripVertical, Settings2 } from "lucide-react";
import { useMemo, useState } from "react";
import {
	Sortable,
	SortableDragHandle,
	SortableItem,
} from "@/components/custom/sortable";
import { useDataTable } from "@/components/data-table/data-table-provider";
import { Button } from "@/components/ui/button";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
} from "@/components/ui/command";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import { boxRadiusClassName } from "@/lib/style";

export function DataTableViewOptions() {
	const { table, enableColumnOrdering } = useDataTable();
	const [open, setOpen] = useState(false);
	const [drag, setDrag] = useState(false);
	const [search, setSearch] = useState("");

	const columnOrder = table.state.columnOrder;

	const sortedColumns = useMemo(
		() =>
			table
				.getAllColumns()
				.sort((a, b) => columnOrder.indexOf(a.id) - columnOrder.indexOf(b.id)),
		[columnOrder, table]
	);

	return (
		<Popover onOpenChange={setOpen} open={open}>
			<PopoverTrigger
				render={
					<Button
						aria-expanded={open}
						className="shadow-none"
						role="combobox"
						size="icon"
						variant="outline"
					/>
				}
			>
				<Settings2 className="h-4 w-4" />
				<span className="sr-only">View</span>
			</PopoverTrigger>
			<PopoverContent align="end" className="w-[200px] p-0" side="bottom">
				<Command>
					<CommandInput
						onValueChange={setSearch}
						placeholder="Search options..."
						value={search}
					/>
					<CommandList>
						<CommandEmpty>No option found.</CommandEmpty>
						<CommandGroup>
							<Sortable
								onDragCancel={() => setDrag(false)}
								onDragEnd={() => setDrag(false)}
								onDragStart={() => setDrag(true)}
								onValueChange={(items) =>
									table.setColumnOrder(items.map((c) => c.id))
								}
								overlay={
									<div
										className={cn("bg-muted/60 h-8 w-full", boxRadiusClassName)}
									/>
								}
								value={sortedColumns.map((c) => ({ id: c.id }))}
							>
								{sortedColumns
									// `getCanHide()` is the single source of truth: columns that
									// must always render (select) declare `enableHiding: false`
									// instead of being special-cased here.
									.filter((column) => column.getCanHide())
									.map((column) => (
										<SortableItem
											key={column.id}
											render={
												<CommandItem
													className={"capitalize"}
													disabled={drag}
													onSelect={() =>
														column.toggleVisibility(!column.getIsVisible())
													}
													value={column.id}
												/>
											}
											value={column.id}
										>
											<div
												className={cn(
													"border-input flex h-4 w-4 items-center justify-center rounded-sm border",
													column.getIsVisible()
														? "bg-primary text-primary-foreground"
														: "opacity-50 [&_svg]:invisible"
												)}
											>
												<Check className={cn("text-background size-3")} />
											</div>
											<span>{column.columnDef.meta?.label || column.id}</span>
											<span className="hidden" data-slot="command-shortcut" />
											{enableColumnOrdering && !search ? (
												<SortableDragHandle
													className="text-muted-foreground hover:text-foreground focus:bg-muted focus:text-foreground ml-auto size-5"
													size="icon"
													variant="ghost"
												>
													<GripVertical aria-hidden="true" className="size-4" />
												</SortableDragHandle>
											) : null}
										</SortableItem>
									))}
							</Sortable>
						</CommandGroup>
					</CommandList>
				</Command>
			</PopoverContent>
		</Popover>
	);
}
