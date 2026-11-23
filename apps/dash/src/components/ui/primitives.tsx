import { cn } from "@securefabric/ui/lib/utils";
import type * as React from "react";

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
	label: string;
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

export function Card({ className, ...props }: React.ComponentProps<"div">) {
	return (
		<div
			className={cn("border-border bg-card rounded-lg border", className)}
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

export type Tone = "neutral" | "ok" | "warn" | "error" | "busy" | "accent";

const BADGE_TONES: Record<Tone, string> = {
	accent: "bg-ds-accent/10 text-ds-accent",
	busy: "bg-ds-accent/10 text-ds-accent",
	error: "bg-destructive/10 text-destructive",
	neutral: "bg-muted text-muted-foreground",
	ok: "bg-ds-success/10 text-ds-success-text",
	warn: "bg-ds-severity-high/15 text-foreground",
};

export function Badge({
	tone = "neutral",
	className,
	...props
}: React.ComponentProps<"span"> & { tone?: Tone }) {
	return (
		<span
			className={cn(
				"text-2xs inline-flex h-5 shrink-0 items-center gap-1 rounded-full px-2 font-medium whitespace-nowrap",
				BADGE_TONES[tone],
				className
			)}
			{...props}
		/>
	);
}

const DOT_TONES: Record<Tone, string> = {
	accent: "bg-ds-accent",
	busy: "bg-ds-accent animate-pulse",
	error: "bg-ds-warn",
	neutral: "bg-ds-muted",
	ok: "bg-ds-success",
	warn: "bg-ds-severity-high",
};

export function Dot({
	tone = "neutral",
	className,
}: {
	tone?: Tone;
	className?: string;
}) {
	return (
		<span
			aria-hidden="true"
			className={cn(
				"inline-block size-2 shrink-0 rounded-full",
				DOT_TONES[tone],
				className
			)}
		/>
	);
}

export function Kbd({ className, ...props }: React.ComponentProps<"kbd">) {
	return (
		<kbd
			className={cn(
				"border-border bg-muted text-2xs text-muted-foreground inline-flex h-5 items-center rounded border px-1.5 font-mono",
				className
			)}
			{...props}
		/>
	);
}

export function Table({ className, ...props }: React.ComponentProps<"table">) {
	return (
		<div className="w-full overflow-x-auto">
			<table className={cn("w-full text-sm", className)} {...props} />
		</div>
	);
}

export function Th({ className, ...props }: React.ComponentProps<"th">) {
	return (
		<th
			className={cn(
				"border-border text-muted-foreground h-10 border-b px-4 text-left text-xs font-medium whitespace-nowrap first:pl-5 last:pr-5",
				className
			)}
			{...props}
		/>
	);
}

export function Td({ className, ...props }: React.ComponentProps<"td">) {
	return (
		<td
			className={cn(
				"border-border h-12 border-b px-4 align-middle group-last/row:border-b-0 first:pl-5 last:pr-5",
				className
			)}
			{...props}
		/>
	);
}

export function Tr({ className, ...props }: React.ComponentProps<"tr">) {
	return (
		<tr
			className={cn("group/row hover:bg-ds-shell transition-colors", className)}
			{...props}
		/>
	);
}

export function Skeleton({ className }: { className?: string }) {
	return <div className={cn("bg-muted animate-pulse rounded-md", className)} />;
}

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

export function Mono({ className, ...props }: React.ComponentProps<"span">) {
	return <span className={cn("text-code font-mono", className)} {...props} />;
}
