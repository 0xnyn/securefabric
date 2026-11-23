"use client";

import { Select as SelectPrimitive } from "@base-ui/react/select";
import { CheckIcon, ChevronsUpDownIcon } from "lucide-react";
import type * as React from "react";
import { cn } from "../lib/utils";

// ---------------------------------------------------------------------------
// Dialog

// ---------------------------------------------------------------------------
// Select

export interface Option<T extends string = string> {
	description?: string;
	label: React.ReactNode;
	value: T;
}

export function Select<T extends string>({
	value,
	onChange,
	options,
	className,
	placeholder,
	ariaLabel,
	size = "md",
	disabled = false,
}: {
	disabled?: boolean;
	value: T;
	onChange: (value: T) => void;
	options: Option<T>[];
	className?: string;
	placeholder?: string;
	ariaLabel?: string;
	size?: "sm" | "md";
}) {
	const items = options.map((o) => ({ label: o.label, value: o.value }));
	return (
		<SelectPrimitive.Root
			disabled={disabled}
			items={items}
			onValueChange={(v) => {
				if (v !== null) {
					onChange(v as T);
				}
			}}
			value={value}
		>
			<SelectPrimitive.Trigger
				aria-label={ariaLabel}
				className={cn(
					"border-input bg-background hover:bg-muted/60 focus-visible:ring-ring/20 inline-flex w-full min-w-0 items-center justify-between gap-2 rounded-md border px-3 text-left text-sm outline-none focus-visible:ring-2 data-disabled:pointer-events-none data-disabled:opacity-60",
					size === "sm" ? "h-8" : "h-9",
					className
				)}
			>
				<span className="truncate">
					<SelectPrimitive.Value placeholder={placeholder} />
				</span>
				<SelectPrimitive.Icon className="text-muted-foreground">
					<ChevronsUpDownIcon className="size-3.5" />
				</SelectPrimitive.Icon>
			</SelectPrimitive.Trigger>
			<SelectPrimitive.Portal>
				<SelectPrimitive.Positioner
					alignItemWithTrigger={false}
					className="z-50 outline-none"
					sideOffset={4}
				>
					<SelectPrimitive.Popup className="border-border bg-popover shadow-float max-h-(--available-height) min-w-(--anchor-width) overflow-y-auto rounded-lg border p-1 transition-opacity duration-100 outline-none data-ending-style:opacity-0 data-starting-style:opacity-0">
						{options.map((o) => (
							<SelectPrimitive.Item
								className="data-highlighted:bg-muted relative flex cursor-default items-center gap-2 rounded-md py-1.5 pr-8 pl-2 text-sm outline-none select-none"
								key={o.value}
								value={o.value}
							>
								<div className="grid min-w-0">
									<SelectPrimitive.ItemText className="truncate">
										{o.label}
									</SelectPrimitive.ItemText>
									{o.description ? (
										<span className="text-muted-foreground truncate text-xs">
											{o.description}
										</span>
									) : null}
								</div>
								<SelectPrimitive.ItemIndicator className="absolute right-2">
									<CheckIcon className="size-3.5" />
								</SelectPrimitive.ItemIndicator>
							</SelectPrimitive.Item>
						))}
					</SelectPrimitive.Popup>
				</SelectPrimitive.Positioner>
			</SelectPrimitive.Portal>
		</SelectPrimitive.Root>
	);
}
