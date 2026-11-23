import type * as React from "react";
import { cn } from "../lib/utils";

export function Card({ className, ...props }: React.ComponentProps<"div">) {
	return (
		<div
			className={cn("border-border bg-card rounded-lg border", className)}
			data-slot="card"
			{...props}
		/>
	);
}

export function CardHeader({
	title,
	description,
	action,
	className,
}: {
	title: React.ReactNode;
	description?: React.ReactNode;
	action?: React.ReactNode;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"border-border flex items-start justify-between gap-4 border-b px-5 py-4",
				className
			)}
		>
			<div className="grid gap-0.5">
				<h3 className="text-sm font-medium">{title}</h3>
				{description ? (
					<p className="text-muted-foreground text-sm">{description}</p>
				) : null}
			</div>
			{action}
		</div>
	);
}

export function CardFooter({
	className,
	...props
}: React.ComponentProps<"div">) {
	return (
		<div
			className={cn(
				"border-border bg-ds-shell text-muted-foreground flex items-center justify-between gap-4 rounded-b-lg border-t px-5 py-3 text-sm",
				className
			)}
			{...props}
		/>
	);
}
