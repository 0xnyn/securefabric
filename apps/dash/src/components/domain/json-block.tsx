"use client";

import { cn } from "@securefabric/ui/lib/utils";

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
