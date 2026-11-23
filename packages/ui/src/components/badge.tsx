import type * as React from "react";
import { cn } from "../lib/utils";

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
