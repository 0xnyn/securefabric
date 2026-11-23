"use client";

import { Badge, Dot, type Tone } from "@securefabric/ui/components/badge";
import { cn } from "@securefabric/ui/lib/utils";
import { type Health, healthInfo } from "@/lib/types";

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

/** "RETRY_WAIT" → "Retry wait", "success" → "Success": sentence case for an enum. */
export function enumLabel(value: string): string {
	const words = value.replaceAll("_", " ").toLowerCase();
	return words.charAt(0).toUpperCase() + words.slice(1);
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
	return <Badge tone={tones[value] ?? "neutral"}>{enumLabel(value)}</Badge>;
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
