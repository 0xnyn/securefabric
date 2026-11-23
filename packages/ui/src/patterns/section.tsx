"use client";

import { cn } from "../lib/utils";

export function Section({
	title,
	description,
	action,
	children,
	className,
}: {
	title: React.ReactNode;
	description?: React.ReactNode;
	action?: React.ReactNode;
	children: React.ReactNode;
	className?: string;
}) {
	return (
		// Header row, then the body takes the rest: side by side in a grid, two
		// sections' cards end at the same height whatever they hold.
		<section className={cn("grid grid-rows-[auto_1fr] gap-3", className)}>
			<div className="flex min-h-8 items-end justify-between gap-4">
				<div className="grid gap-0.5">
					<h2 className="text-base font-semibold">{title}</h2>
					{description ? (
						<p className="text-muted-foreground text-sm">{description}</p>
					) : null}
				</div>
				{action}
			</div>
			{children}
		</section>
	);
}
