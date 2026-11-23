"use client";

import { UTCDate } from "@date-fns/utc";
import { cn } from "@securefabric/ui/lib/utils";
import { format, formatDistanceToNowStrict } from "date-fns";
import { Check, Copy } from "lucide-react";
import type { ComponentPropsWithoutRef } from "react";
import { HOVER_CARD_DELAY } from "@/components/data-table/ui-compat";
import {
	HoverCard,
	HoverCardContent,
	HoverCardTrigger,
} from "@/components/ui/hover-card";
import { useCopyToClipboard } from "@/hooks/use-copy-to-clipboard";

type HoverCardContentProps = ComponentPropsWithoutRef<typeof HoverCardContent>;

interface HoverCardTimestampProps {
	align?: HoverCardContentProps["align"];
	alignOffset?: HoverCardContentProps["alignOffset"];
	className?: string;
	date: Date;
	side?: HoverCardContentProps["side"];
	sideOffset?: HoverCardContentProps["sideOffset"];
}

export function HoverCardTimestamp({
	date,
	side = "right",
	align = "start",
	alignOffset = -4,
	sideOffset,
	className,
}: HoverCardTimestampProps) {
	const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

	return (
		<HoverCard {...HOVER_CARD_DELAY}>
			<HoverCardTrigger
				render={
					<div className={cn("font-mono whitespace-nowrap", className)} />
				}
			>
				{format(date, "LLL dd, y HH:mm:ss")}
			</HoverCardTrigger>
			{/* Portal is built into HoverCardContent in shadcn v4 */}
			<HoverCardContent
				className="z-10 w-auto p-2"
				{...{ align, alignOffset, side, sideOffset }}
			>
				<dl className="flex flex-col gap-1">
					<Row label="Timestamp" value={String(date.getTime())} />
					<Row
						label="UTC"
						value={format(new UTCDate(date), "LLL dd, y HH:mm:ss")}
					/>
					<Row label={timezone} value={format(date, "LLL dd, y HH:mm:ss")} />
					<Row
						label="Relative"
						value={formatDistanceToNowStrict(date, { addSuffix: true })}
					/>
				</dl>
			</HoverCardContent>
		</HoverCard>
	);
}

function Row({ value, label }: { value: string; label: string }) {
	const { copy, isCopied } = useCopyToClipboard();

	return (
		<div
			className="group flex items-center justify-between gap-4 text-sm"
			onClick={(e) => {
				e.stopPropagation();
				copy(value);
			}}
		>
			<dt className="text-muted-foreground">{label}</dt>
			<dd className="flex items-center gap-1 truncate font-mono">
				<span className="invisible group-hover:visible">
					{isCopied ? (
						<Check className="h-3 w-3" />
					) : (
						<Copy className="h-3 w-3" />
					)}
				</span>
				{value}
			</dd>
		</div>
	);
}
