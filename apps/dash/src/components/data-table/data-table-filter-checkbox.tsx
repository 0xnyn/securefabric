"use client";

import { cn } from "@securefabric/ui/lib/utils";
import { Checkbox } from "@securefabric/ui/primitives/checkbox";
import {
	InputGroup,
	InputGroupAddon,
	InputGroupInput,
} from "@securefabric/ui/primitives/input-group";
import { Label } from "@securefabric/ui/primitives/label";
import { Skeleton } from "@securefabric/ui/primitives/skeleton";
import { Search } from "lucide-react";
import { useState } from "react";
import { useDataTable } from "@/components/data-table/data-table-provider";
import { boxRadiusClassName, boxSurfaceClassName } from "@/lib/style";
import { formatCompactNumber } from "@/lib/table/format";
import type { DataTableCheckboxFilterField } from "./types";

export function DataTableFilterCheckbox<TData>({
	value: _value,
	options,
	component,
}: DataTableCheckboxFilterField<TData>) {
	const value = _value as string;
	const [inputValue, setInputValue] = useState("");
	const { table, columnFilters, isLoading, getFacetedUniqueValues } =
		useDataTable();
	const column = table.getColumn(value);
	// REMINDER: avoid using column?.getFilterValue()
	const filterValue = columnFilters.find((i) => i.id === value)?.value;
	const facetedValue =
		getFacetedUniqueValues?.(table, value) || column?.getFacetedUniqueValues();

	const Component = component;

	// filter out the options based on the input value
	const filterOptions = options?.filter(
		(option) =>
			inputValue === "" ||
			option.label.toLowerCase().includes(inputValue.toLowerCase())
	);

	// CHECK: it could be filterValue or searchValue
	const filters = filterValue
		? Array.isArray(filterValue)
			? filterValue
			: [filterValue]
		: [];

	// REMINDER: if no options are defined, while fetching data, we should show a skeleton
	if (isLoading && !filterOptions?.length) {
		return (
			<div className={cn("grid divide-y border", boxSurfaceClassName)}>
				{Array.from({ length: 3 }).map((_, index) => (
					<div
						className="flex items-center justify-between gap-2 px-2 py-2.5"
						key={index}
					>
						<Skeleton className="h-4 w-4" />
						<Skeleton className="h-4 w-full" />
					</div>
				))}
			</div>
		);
	}

	// Facets come from the rows, so an empty table has nothing to offer. Say so
	// rather than leave an open section with a blank gap under it.
	if (!options?.length) {
		return <p className="text-muted-foreground px-2 pb-1 text-sm">None yet</p>;
	}

	return (
		<div className="grid gap-2">
			{options.length > 4 ? (
				<InputGroup className="h-9 shadow-none">
					<InputGroupAddon>
						<Search className="mt-0.5 h-4 w-4" />
					</InputGroupAddon>
					<InputGroupInput
						onChange={(e) => setInputValue(e.target.value)}
						placeholder="Search"
						value={inputValue}
					/>
				</InputGroup>
			) : null}
			{/*
        No max-height of its own: the filter panel already scrolls, and a box
        that scrolls inside a list that scrolls is a second scrollbar for
        nothing. The search box above narrows long lists instead.
      */}
			<div
				className={cn(
					"overflow-hidden border empty:border-none",
					boxSurfaceClassName
				)}
			>
				{filterOptions
					// TODO: we shoudn't sort the options here, instead filterOptions should be sorted by default
					// .sort((a, b) => a.label.localeCompare(b.label))
					?.map((option, index) => {
						const checked = filters.includes(option.value);

						return (
							<div
								className={cn(
									"group hover:bg-accent/50 relative flex items-center space-x-2 px-2 py-2.5",
									index === filterOptions.length - 1 ? undefined : "border-b"
								)}
								key={String(option.value)}
							>
								<Checkbox
									checked={checked}
									id={`${value}-${option.value}`}
									onCheckedChange={(checked) => {
										const newValue = checked
											? [...(filters || []), option.value]
											: filters?.filter((value) => option.value !== value);
										column?.setFilterValue(
											newValue?.length ? newValue : undefined
										);
									}}
								/>
								<Label
									className="text-foreground/70 group-hover:text-accent-foreground flex w-full items-center justify-center gap-1 truncate"
									htmlFor={`${value}-${option.value}`}
								>
									{Component ? (
										<Component {...option} options={options} />
									) : (
										<span className="truncate font-normal">{option.label}</span>
									)}
									{/*
                    The count and "Only" share one slot: hover or focus the row
                    and the count gives way, so the two never overlap.
                  */}
									<span className="ml-auto flex items-center justify-center font-mono text-xs group-focus-within:hidden group-hover:hidden">
										{isLoading ? (
											<Skeleton className="h-4 w-4" />
										) : facetedValue?.has(option.value) ? (
											formatCompactNumber(facetedValue.get(option.value) || 0)
										) : null}
									</span>
									<button
										aria-label={`Only ${option.label}`}
										className={cn(
											"text-muted-foreground hover:text-foreground ml-auto hidden px-1 text-xs font-normal group-focus-within:block group-hover:block",
											"focus-visible:ring-ring/50 outline-none focus-visible:ring-[3px]",
											boxRadiusClassName
										)}
										onClick={() => column?.setFilterValue([option.value])}
										type="button"
									>
										Only
									</button>
								</Label>
							</div>
						);
					})}
			</div>
		</div>
	);
}
