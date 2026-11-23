"use client";

import { cn } from "../lib/utils";

// ---------------------------------------------------------------------------
// Copy

// ---------------------------------------------------------------------------
// Layout

export function PageHeader({
	title,
	description,
	actions,
	children,
}: {
	title: React.ReactNode;
	description?: React.ReactNode;
	actions?: React.ReactNode;
	children?: React.ReactNode;
}) {
	return (
		<div className="border-border bg-background border-b">
			<div className="flex flex-col gap-4 px-4 py-7 sm:flex-row sm:items-end sm:justify-between sm:px-8">
				<div className="grid min-w-0 gap-1.5">
					<h1 className="tracking-heading text-2xl font-semibold">{title}</h1>
					{description ? (
						<p className="text-muted-foreground max-w-2xl text-sm">
							{description}
						</p>
					) : null}
				</div>
				{actions ? (
					<div className="flex shrink-0 flex-wrap items-center gap-2">
						{actions}
					</div>
				) : null}
			</div>
			{children}
		</div>
	);
}

export function PageBody({
	className,
	children,
}: {
	className?: string;
	children: React.ReactNode;
}) {
	return (
		<div className={cn("w-full px-4 py-7 sm:px-8", className)}>{children}</div>
	);
}
