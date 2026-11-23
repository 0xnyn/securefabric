"use client";

import { Tooltip } from "@securefabric/ui/components/tooltip";
import { dateTime, timeAgo } from "@securefabric/ui/lib/format";
import { cn } from "@securefabric/ui/lib/utils";

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
