"use client";

import {
	InputGroup,
	InputGroupAddon,
	InputGroupInput,
} from "@securefabric/ui/primitives/input-group";
import { Label } from "@securefabric/ui/primitives/label";
import { useEffect, useState } from "react";
import { useDataTable } from "@/components/data-table/data-table-provider";
import { Slider } from "@/components/data-table/ui/slider";
import { useDebounce } from "@/hooks/use-debounce";
import { isArrayOfNumbers } from "@/lib/is-array";
import type { DataTableSliderFilterField } from "./types";

function getFilter(filterValue: unknown) {
	return typeof filterValue === "number"
		? [filterValue, filterValue]
		: Array.isArray(filterValue) && isArrayOfNumbers(filterValue)
			? filterValue.length === 1
				? [filterValue[0], filterValue[0]]
				: filterValue
			: null;
}

// TODO: discuss if we even need the `defaultMin` and `defaultMax`
export function DataTableFilterSlider<TData>({
	value: _value,
	min: defaultMin,
	max: defaultMax,
	unit,
}: DataTableSliderFilterField<TData>) {
	const value = _value as string;
	const { table, columnFilters, getFacetedMinMaxValues } = useDataTable();
	const column = table.getColumn(value);
	const filterValue = columnFilters.find((i) => i.id === value)?.value;
	const filters = getFilter(filterValue);
	const [input, setInput] = useState<number[] | null>(filters);
	const [min, max] = getFacetedMinMaxValues?.(table, value) ||
		column?.getFacetedMinMaxValues() || [defaultMin, defaultMax];

	const debouncedInput = useDebounce(input, 500);

	useEffect(() => {
		if (debouncedInput?.length === 2) {
			column?.setFilterValue(debouncedInput);
		}
	}, [debouncedInput]);

	useEffect(() => {
		if (debouncedInput?.length !== 2) {
		} else if (!filters) {
			setInput(null);
		} else if (
			debouncedInput[0] !== filters[0] ||
			debouncedInput[1] !== filters[1]
		) {
			setInput(filters);
		}
	}, [filters]);

	return (
		<div className="grid gap-2">
			<div className="flex items-center gap-4">
				<div className="grid w-full gap-1.5">
					<Label
						className="text-muted-foreground px-2"
						htmlFor={`min-${value}`}
					>
						Min.
					</Label>
					<InputGroup className="mb-2 h-9 font-mono shadow-none">
						<InputGroupInput
							id={`min-${value}`}
							max={max}
							min={min}
							name={`min-${value}`}
							onChange={(e) =>
								setInput((prev) => [Number(e.target.value), prev?.[1] || max])
							}
							placeholder="from"
							type="number"
							value={`${input?.[0] ?? min}`}
						/>
						{unit ? (
							<InputGroupAddon align="inline-end">{unit}</InputGroupAddon>
						) : null}
					</InputGroup>
				</div>
				<div className="grid w-full gap-1.5">
					<Label
						className="text-muted-foreground px-2"
						htmlFor={`max-${value}`}
					>
						Max.
					</Label>
					<InputGroup className="mb-2 h-9 font-mono shadow-none">
						<InputGroupInput
							id={`max-${value}`}
							max={max}
							min={min}
							name={`max-${value}`}
							onChange={(e) =>
								setInput((prev) => [prev?.[0] || min, Number(e.target.value)])
							}
							placeholder="to"
							type="number"
							value={`${input?.[1] ?? max}`}
						/>
						{unit ? (
							<InputGroupAddon align="inline-end">{unit}</InputGroupAddon>
						) : null}
					</InputGroup>
				</div>
			</div>
			<Slider
				max={max}
				min={min}
				onValueChange={(values) => setInput(values)}
				value={input?.length === 2 ? input : [min, max]}
			/>
		</div>
	);
}
