import type * as React from "react";
import { cn } from "../lib/utils";

export function EmptyState({
	icon,
	title,
	description,
	action,
	className,
}: {
	icon?: React.ReactNode;
	title: string;
	description: React.ReactNode;
	action?: React.ReactNode;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"border-border flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-16 text-center",
				// Inside a card the card is the frame: no second border, fill it,
				// and centre in whatever height the row gives it.
				"in-data-[slot=card]:h-full in-data-[slot=card]:min-h-48 in-data-[slot=card]:rounded-none in-data-[slot=card]:border-0 in-data-[slot=card]:py-8",
				className
			)}
		>
			{icon ? (
				<div className="border-border bg-background text-muted-foreground flex size-10 items-center justify-center rounded-full border">
					{icon}
				</div>
			) : null}
			<div className="grid gap-1">
				<p className="text-sm font-medium">{title}</p>
				<p className="text-muted-foreground max-w-sm text-sm">{description}</p>
			</div>
			{action}
		</div>
	);
}
