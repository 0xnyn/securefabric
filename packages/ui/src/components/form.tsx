import type * as React from "react";
import { cn } from "../lib/utils";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
	return (
		<input
			className={cn(
				"border-input bg-background placeholder:text-muted-foreground focus-visible:border-ds-muted focus-visible:ring-ring/20 aria-invalid:border-destructive h-9 w-full min-w-0 rounded-md border px-3 text-sm transition-colors outline-none focus-visible:ring-2 disabled:opacity-60",
				className
			)}
			{...props}
		/>
	);
}

export function Textarea({
	className,
	...props
}: React.ComponentProps<"textarea">) {
	return (
		<textarea
			className={cn(
				"border-input bg-background placeholder:text-muted-foreground focus-visible:border-ds-muted focus-visible:ring-ring/20 min-h-20 w-full rounded-md border px-3 py-2 text-sm outline-none focus-visible:ring-2",
				className
			)}
			{...props}
		/>
	);
}

export function Label({ className, ...props }: React.ComponentProps<"label">) {
	return (
		// biome-ignore lint/a11y/noLabelWithoutControl: callers pass htmlFor or nest the control.
		<label
			className={cn("text-foreground text-sm font-medium", className)}
			{...props}
		/>
	);
}

export function Field({
	label,
	htmlFor,
	help,
	children,
	className,
}: {
	label: React.ReactNode;
	htmlFor?: string;
	help?: React.ReactNode;
	children: React.ReactNode;
	className?: string;
}) {
	return (
		<div className={cn("grid gap-1.5", className)}>
			<Label htmlFor={htmlFor}>{label}</Label>
			{children}
			{help ? <p className="text-muted-foreground text-xs">{help}</p> : null}
		</div>
	);
}
