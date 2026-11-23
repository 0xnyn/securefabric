"use client";

import { cn } from "../lib/utils";

// ---------------------------------------------------------------------------
// Copy

export function KeyValue({
	items,
	className,
}: {
	items: { label: string; value: React.ReactNode }[];
	className?: string;
}) {
	return (
		<dl className={cn("grid gap-x-6 gap-y-4 sm:grid-cols-2", className)}>
			{items.map((item) => (
				<div className="grid min-w-0 gap-1" key={item.label}>
					<dt className="text-muted-foreground text-xs">{item.label}</dt>
					<dd className="min-w-0 truncate text-sm">{item.value}</dd>
				</div>
			))}
		</dl>
	);
}
