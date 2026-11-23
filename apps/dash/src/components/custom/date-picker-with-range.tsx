"use client";

import { cn } from "@securefabric/ui/lib/utils";
import { format } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import * as React from "react";
import type { DateRange } from "react-day-picker";
import type { DatePreset } from "@/components/data-table/types";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import { Label } from "@/components/ui/label";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "@/components/ui/popover";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { useDebounce } from "@/hooks/use-debounce";
import { presets as defaultPresets } from "@/lib/date-preset";

interface DatePickerWithRangeProps
	extends React.HTMLAttributes<HTMLDivElement> {
	date: DateRange | undefined;
	presets?: DatePreset[];
	setDate: (date: DateRange | undefined) => void;
}

export function DatePickerWithRange({
	className,
	date,
	setDate,
	presets = defaultPresets,
}: DatePickerWithRangeProps) {
	const [open, setOpen] = React.useState(false);
	React.useEffect(() => {
		const down = (e: KeyboardEvent) => {
			if (!open) {
				return;
			}

			presets.map((preset) => {
				if (preset.shortcut === e.key) {
					setDate({ from: preset.from, to: preset.to });
				}
			});
		};
		document.addEventListener("keydown", down);
		return () => document.removeEventListener("keydown", down);
	}, [setDate, presets, open]);

	return (
		<div className={cn("grid gap-2", className)}>
			<Popover onOpenChange={setOpen} open={open}>
				<PopoverTrigger
					render={
						<Button
							className={cn(
								"hover:bg-muted/50 max-w-full justify-start truncate text-left font-normal shadow-none",
								!date && "text-muted-foreground"
							)}
							id="date"
							variant="outline"
						/>
					}
				>
					<CalendarIcon className="h-4 w-4" />
					{date?.from ? (
						date.to ? (
							<span className="truncate">
								{format(date.from, "LLL dd, y")} -{" "}
								{format(date.to, "LLL dd, y")}
							</span>
						) : (
							format(date.from, "LLL dd, y")
						)
					) : (
						<span>Pick a date</span>
					)}
				</PopoverTrigger>
				<PopoverContent align="start" className="w-auto p-0">
					<div className="flex flex-col justify-between sm:flex-row">
						<div className="hidden sm:block">
							<DatePresets
								onSelect={setDate}
								presets={presets}
								selected={date}
							/>
						</div>
						<div className="block p-3 sm:hidden">
							<DatePresetsSelect
								onSelect={setDate}
								presets={presets}
								selected={date}
							/>
						</div>
						<Separator className="h-auto w-px" orientation="vertical" />
						<Calendar
							// `initialFocus` until react-day-picker 9 deprecated it; gone in
							// 10, which is what shadcn's `calendar` installs today.
							autoFocus
							defaultMonth={date?.from}
							mode="range"
							numberOfMonths={1}
							onSelect={setDate}
							selected={date}
						/>
					</div>
					<Separator />
					<CustomDateRange onSelect={setDate} selected={date} />
				</PopoverContent>
			</Popover>
		</div>
	);
}

function DatePresets({
	selected,
	onSelect,
	presets,
}: {
	selected: DateRange | undefined;
	onSelect: (date: DateRange | undefined) => void;
	presets: DatePreset[];
}) {
	return (
		<div className="flex flex-col gap-2 p-3">
			<p className="text-muted-foreground mx-3 text-xs uppercase">Date Range</p>
			<div className="grid gap-1">
				{presets.map(({ label, shortcut, from, to }) => {
					const isActive = selected?.from === from && selected?.to === to;
					return (
						<Button
							className={cn(
								"flex items-center justify-between gap-6",
								!isActive && "border border-transparent!"
							)}
							key={label}
							onClick={() => onSelect({ from, to })}
							variant={isActive ? "outline" : "ghost"}
						>
							<span className="mr-auto">{label}</span>
							<Kbd className="uppercase">{shortcut}</Kbd>
						</Button>
					);
				})}
			</div>
		</div>
	);
}

function DatePresetsSelect({
	selected,
	onSelect,
	presets,
}: {
	selected: DateRange | undefined;
	onSelect: (date: DateRange | undefined) => void;
	presets: DatePreset[];
}) {
	function findPreset(from?: Date, to?: Date) {
		return presets.find((p) => p.from === from && p.to === to)?.shortcut;
	}
	const [value, setValue] = React.useState<string | undefined>(
		findPreset(selected?.from, selected?.to)
	);

	React.useEffect(() => {
		const preset = findPreset(selected?.from, selected?.to);
		if (preset === value) {
			return;
		}
		setValue(preset);
	}, [selected, presets]);

	return (
		<Select
			onValueChange={(v) => {
				const preset = presets.find((p) => p.shortcut === v);
				if (preset) {
					onSelect({ from: preset.from, to: preset.to });
				}
			}}
			value={value}
		>
			{/* REMINDER: the label is rendered here rather than through the select
          value's placeholder. Base UI has no `placeholder` prop there — it
          reads the label off the root's `items` array — and `placeholder` is a
          valid HTML attribute, so passing it typechecks and then renders an
          empty trigger. Picking the muted colour by hand keeps the placeholder
          looking the same on both libraries. */}
			<SelectTrigger className={cn(!value && "text-muted-foreground")}>
				{presets.find((preset) => preset.shortcut === value)?.label ??
					"Date Presets"}
			</SelectTrigger>
			<SelectContent>
				<SelectGroup>
					<SelectLabel>Date Presets</SelectLabel>
					{presets.map(({ label, shortcut }) => (
						<SelectItem
							className="flex items-center justify-between [&>span:last-child]:flex [&>span:last-child]:w-full [&>span:last-child]:justify-between"
							key={label}
							value={shortcut}
						>
							<span>{label}</span>
							<Kbd className="ml-2 uppercase">{shortcut}</Kbd>
						</SelectItem>
					))}
				</SelectGroup>
			</SelectContent>
		</Select>
	);
}

// REMINDER: We can add min max date range validation https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/datetime-local#setting_maximum_and_minimum_dates_and_times
function CustomDateRange({
	selected,
	onSelect,
}: {
	selected: DateRange | undefined;
	onSelect: (date: DateRange | undefined) => void;
}) {
	const [dateFrom, setDateFrom] = React.useState<Date | undefined>(
		selected?.from
	);
	const [dateTo, setDateTo] = React.useState<Date | undefined>(selected?.to);
	const debounceDateFrom = useDebounce(dateFrom, 1000);
	const debounceDateTo = useDebounce(dateTo, 1000);

	const formatDateForInput = (date: Date | undefined): string => {
		if (!date) {
			return "";
		}
		const utcDate = new Date(
			date.getTime() - date.getTimezoneOffset() * 60_000
		);
		return utcDate.toISOString().slice(0, 16);
	};

	React.useEffect(() => {
		onSelect({ from: debounceDateFrom, to: debounceDateTo });
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [debounceDateFrom, debounceDateTo]);

	return (
		<div className="flex flex-col gap-2 p-3">
			<p className="text-muted-foreground text-xs uppercase">Custom Range</p>
			<div className="grid gap-2 sm:grid-cols-2">
				<div className="grid w-full gap-1.5">
					<Label htmlFor="from">Start</Label>
					<Input
						defaultValue={formatDateForInput(selected?.from)}
						disabled={!selected?.from}
						id="from"
						key={formatDateForInput(selected?.from)}
						name="from"
						onChange={(e) => {
							const newDate = new Date(e.target.value);
							if (!Number.isNaN(newDate.getTime())) {
								setDateFrom(newDate);
							}
						}}
						type="datetime-local"
					/>
				</div>
				<div className="grid w-full gap-1.5">
					<Label htmlFor="to">End</Label>
					<Input
						defaultValue={formatDateForInput(selected?.to)}
						disabled={!selected?.to}
						id="to"
						key={formatDateForInput(selected?.to)}
						name="to"
						onChange={(e) => {
							const newDate = new Date(e.target.value);
							if (!Number.isNaN(newDate.getTime())) {
								setDateTo(newDate);
							}
						}}
						type="datetime-local"
					/>
				</div>
			</div>
		</div>
	);
}
