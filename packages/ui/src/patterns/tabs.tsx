"use client";

import { cn } from "../lib/utils";

// ---------------------------------------------------------------------------
// Copy

/** Underlined tabs, Vercel style, for sections inside a page. */
export function Tabs<T extends string>({
	tabs,
	value,
	onChange,
	className,
}: {
	tabs: { value: T; label: React.ReactNode; count?: number }[];
	value: T;
	onChange: (value: T) => void;
	className?: string;
}) {
	return (
		<div
			className={cn(
				"border-border -mb-px flex gap-1 overflow-x-auto border-b",
				className
			)}
			role="tablist"
		>
			{tabs.map((t) => {
				const active = t.value === value;
				return (
					<button
						aria-selected={active}
						className={cn(
							"relative flex h-10 shrink-0 items-center gap-1.5 px-3 text-sm transition-colors",
							active
								? "text-foreground after:bg-foreground after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full"
								: "text-muted-foreground hover:text-foreground"
						)}
						key={t.value}
						onClick={() => onChange(t.value)}
						role="tab"
						type="button"
					>
						{t.label}
						{t.count === undefined ? null : (
							<span className="bg-muted text-2xs text-muted-foreground rounded-full px-1.5">
								{t.count}
							</span>
						)}
					</button>
				);
			})}
		</div>
	);
}
