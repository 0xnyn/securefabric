"use client";

import { ClientResponseError } from "@securefabric/client";
import { cn } from "@securefabric/ui/lib/utils";
import { ChevronLeftIcon, ChevronRightIcon, RefreshCwIcon } from "lucide-react";
import Image from "next/image";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, Tooltip } from "@/components/ui/overlay";
import {
	Badge,
	Dot,
	EmptyState,
	Skeleton,
	type Tone,
} from "@/components/ui/primitives";
import { dateTime, timeAgo } from "@/lib/format";
import { CONNECTOR_LOGOS, type Health, healthInfo } from "@/lib/types";

/** A human sentence for any error, with the API's request id when there is one. */
export function errorText(error: unknown): string {
	if (error instanceof ClientResponseError) {
		const fields = error.errors
			.map((e) => `${e.field}: ${e.message}`)
			.join("; ");
		return [
			error.message,
			fields,
			error.requestId ? `(${error.requestId})` : "",
		]
			.filter(Boolean)
			.join(" ");
	}
	return error instanceof Error ? error.message : String(error);
}

export function ms(value: string | null | undefined): number | null {
	return value ? new Date(value).getTime() : null;
}

/** "3 minutes ago", with the full timestamp on hover. */
export function When({
	value,
	className,
}: {
	value: string | null | undefined;
	className?: string;
}) {
	const t = ms(value);
	if (t === null) {
		return <span className={cn("text-muted-foreground", className)}>—</span>;
	}
	return (
		<Tooltip content={dateTime(t)}>
			<span className={cn("whitespace-nowrap", className)}>{timeAgo(t)}</span>
		</Tooltip>
	);
}

export function HealthBadge({
	health,
}: {
	health: Pick<Health, "name"> | string;
}) {
	const code = typeof health === "string" ? health : health.name;
	const info = healthInfo(code);
	return (
		<Badge tone={info.tone}>
			<Dot className="size-1.5" tone={info.tone} />
			{info.label}
		</Badge>
	);
}

export function StatusBadge({
	value,
	tones,
}: {
	value: string | null | undefined;
	tones: Record<string, Tone>;
}) {
	if (!value) {
		return <span className="text-muted-foreground">—</span>;
	}
	return (
		<Badge tone={tones[value] ?? "neutral"}>
			{value.replaceAll("_", " ").toLowerCase()}
		</Badge>
	);
}

const SEVERITY_CLASS: Record<string, string> = {
	CRITICAL: "bg-ds-warn",
	HIGH: "bg-ds-severity-high",
	INFO: "bg-ds-line-accent",
	LOW: "bg-ds-muted",
	MEDIUM: "bg-ds-severity-medium",
	UNKNOWN: "bg-muted",
};

export function SeverityLabel({ value }: { value: string }) {
	return (
		<span className="inline-flex items-center gap-1.5 text-sm capitalize">
			<span
				aria-hidden="true"
				className={cn(
					"h-3 w-1 rounded-full",
					SEVERITY_CLASS[value] ?? "bg-muted"
				)}
			/>
			{value.toLowerCase()}
		</span>
	);
}

/** The connector's logo, or its initials. */
export function ConnectorLogo({
	id,
	size = 28,
	logo,
}: {
	id: string;
	size?: number;
	logo?: string | null;
}) {
	const src = logo ?? CONNECTOR_LOGOS[id];
	if (src) {
		return (
			<span
				className="border-border bg-ds-bg inline-flex shrink-0 items-center justify-center overflow-hidden rounded-md border"
				style={{ height: size, padding: Math.round(size * 0.15), width: size }}
			>
				<Image
					alt=""
					className="size-full object-contain"
					height={size}
					src={src}
					unoptimized
					width={size}
				/>
			</span>
		);
	}
	return (
		<span
			aria-hidden="true"
			className="border-border bg-muted text-muted-foreground inline-flex shrink-0 items-center justify-center rounded-md border font-semibold"
			style={{ fontSize: Math.max(9, size * 0.34), height: size, width: size }}
		>
			{id.slice(0, 2)}
		</span>
	);
}

/** Loading, error and empty states for a query, in one place. */
export function QueryState({
	query,
	empty,
	children,
	rows = 4,
}: {
	query: {
		isPending: boolean;
		isError: boolean;
		error: unknown;
		refetch: () => unknown;
	};
	empty?: {
		when: boolean;
		title: string;
		description: React.ReactNode;
		action?: React.ReactNode;
	};
	children: React.ReactNode;
	rows?: number;
}) {
	if (query.isPending) {
		return (
			<div className="grid gap-2">
				{Array.from({ length: rows }, (_, i) => (
					// biome-ignore lint/suspicious/noArrayIndexKey: placeholders have no identity
					<Skeleton className="h-10" key={i} />
				))}
			</div>
		);
	}
	if (query.isError) {
		return (
			<EmptyState
				action={
					<Button onClick={() => query.refetch()} size="sm" variant="outline">
						<RefreshCwIcon /> Retry
					</Button>
				}
				description={errorText(query.error)}
				title="Couldn't load this"
			/>
		);
	}
	if (empty?.when) {
		return (
			<EmptyState
				action={empty.action}
				description={empty.description}
				title={empty.title}
			/>
		);
	}
	return <>{children}</>;
}

/**
 * Keyset paging (API-02): a stack of cursors, so Back returns to exactly the
 * page you saw. `cursor` is what the current request sends.
 */
export function useCursorStack(): {
	cursor: string | undefined;
	page: number;
	next: (c: string | null | undefined) => void;
	prev: () => void;
	reset: () => void;
} {
	const [stack, setStack] = useState<string[]>([]);
	return {
		cursor: stack.at(-1),
		next: (c) => {
			if (c) {
				setStack((s) => [...s, c]);
			}
		},
		page: stack.length + 1,
		prev: () => setStack((s) => s.slice(0, -1)),
		reset: () => setStack([]),
	};
}

export function Pager({
	page,
	hasNext,
	onNext,
	onPrev,
	count,
}: {
	page: number;
	hasNext: boolean;
	onNext: () => void;
	onPrev: () => void;
	count?: number;
}) {
	return (
		<div className="text-muted-foreground flex items-center justify-between gap-2 py-3 text-sm">
			<span>
				Page {page}
				{count === undefined ? null : ` · ${count} shown`}
			</span>
			<div className="flex gap-1">
				<Button
					aria-label="Previous page"
					disabled={page <= 1}
					onClick={onPrev}
					size="sm"
					variant="outline"
				>
					<ChevronLeftIcon /> Previous
				</Button>
				<Button
					aria-label="Next page"
					disabled={!hasNext}
					onClick={onNext}
					size="sm"
					variant="outline"
				>
					Next <ChevronRightIcon />
				</Button>
			</div>
		</div>
	);
}

/** A labelled JSON block for vendor attributes and raw payloads. */
export function JsonBlock({
	value,
	className,
}: {
	value: unknown;
	className?: string;
}) {
	return (
		<pre
			className={cn(
				"border-border bg-ds-shell text-code max-h-96 overflow-auto rounded-md border p-3 font-mono text-xs leading-relaxed",
				className
			)}
		>
			{JSON.stringify(value, null, 2)}
		</pre>
	);
}

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
		<section className={cn("grid gap-3", className)}>
			<div className="flex items-end justify-between gap-4">
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

/** A button that asks before doing something it can't undo. */
export function ConfirmButton({
	title,
	description,
	confirmLabel,
	onConfirm,
	disabled,
	children,
	size = "sm",
	variant = "destructive",
}: {
	title: string;
	description: React.ReactNode;
	confirmLabel: string;
	onConfirm: () => void;
	disabled?: boolean;
	children: React.ReactNode;
	size?: "xs" | "sm";
	variant?: "destructive" | "ghost";
}) {
	const [open, setOpen] = useState(false);
	return (
		<>
			<Button
				disabled={disabled}
				onClick={() => setOpen(true)}
				size={size}
				variant={variant}
			>
				{children}
			</Button>
			<Dialog onOpenChange={setOpen} open={open}>
				<DialogContent
					description={description}
					footer={
						<>
							<Button onClick={() => setOpen(false)}>Cancel</Button>
							<Button
								onClick={() => {
									setOpen(false);
									onConfirm();
								}}
								variant="destructive"
							>
								{confirmLabel}
							</Button>
						</>
					}
					title={title}
				>
					{null}
				</DialogContent>
			</Dialog>
		</>
	);
}
