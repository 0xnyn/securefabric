"use client";

import { cn } from "@securefabric/ui/lib/utils";
import {
	ArrowLeftRightIcon,
	KeyRoundIcon,
	RefreshCwIcon,
	WebhookIcon,
	ZapIcon,
} from "lucide-react";
import Link from "next/link";
import { Sparkline } from "@/components/charts";
import { ProviderLogo } from "@/components/common";
import { useHref } from "@/components/shell/env-context";
import { Badge, Card } from "@/components/ui/primitives";
import { getProvider } from "@/lib/catalog";
import { clock, duration, timeAgo } from "@/lib/format";
import type { Connection, Operation, OperationType } from "@/lib/types";

export function StatTile({
	label,
	value,
	hint,
	spark,
	tone,
}: {
	label: string;
	value: string;
	hint?: React.ReactNode;
	spark?: number[];
	tone?: "error";
}) {
	return (
		<Card className="flex flex-col gap-3 p-5">
			<p className="text-muted-foreground text-sm">{label}</p>
			<p className="tracking-heading text-2xl font-semibold tabular-nums">
				{value}
			</p>
			{spark ? (
				<Sparkline
					color={tone === "error" ? "var(--ds-warn)" : "var(--ds-accent)"}
					values={spark}
				/>
			) : null}
			{hint ? <p className="text-muted-foreground text-xs">{hint}</p> : null}
		</Card>
	);
}

export const OP_TYPE_LABELS: Record<OperationType, string> = {
	action: "Action",
	api: "API",
	auth: "Auth",
	proxy: "Proxy",
	sync: "Sync",
	webhook: "Webhook",
};

const OP_ICONS: Record<OperationType, typeof ZapIcon> = {
	action: ZapIcon,
	api: ArrowLeftRightIcon,
	auth: KeyRoundIcon,
	proxy: ArrowLeftRightIcon,
	sync: RefreshCwIcon,
	webhook: WebhookIcon,
};

export function OpTypeBadge({ type }: { type: OperationType }) {
	const Icon = OP_ICONS[type];
	return (
		<Badge className="gap-1 rounded-md font-mono" tone="neutral">
			<Icon className="size-3" />
			{OP_TYPE_LABELS[type]}
		</Badge>
	);
}

export function opTitle(op: Operation): string {
	if (op.type === "sync") {
		return op.action === "sync.initial" ? "Initial sync" : "Scheduled sync";
	}
	return op.action;
}

/** A compact activity row for Overview and the connection page. */
export function ActivityRow({ op }: { op: Operation }) {
	const href = useHref();
	const failed = op.status === "failed";
	return (
		<Link
			className="hover:bg-ds-shell flex items-center gap-3 px-5 py-3 text-sm transition-colors"
			href={href(`/logs?uuid=${op.id}`)}
		>
			<span
				aria-hidden="true"
				className={cn(
					"size-2 shrink-0 rounded-full",
					failed ? "bg-ds-warn" : "bg-ds-success"
				)}
			/>
			<span className="sr-only">{failed ? "Failed" : "Succeeded"}</span>
			{op.provider ? <ProviderLogo provider={op.provider} size={20} /> : null}
			<span className="min-w-0 flex-1 truncate">
				<span className="text-code font-mono">{opTitle(op)}</span>
				{op.customer ? (
					<span className="text-muted-foreground"> · {op.customer}</span>
				) : null}
			</span>
			<span className="text-muted-foreground hidden text-xs tabular-nums sm:inline">
				{duration(op.durationMs)}
			</span>
			<span
				className="text-muted-foreground w-16 text-right text-xs tabular-nums"
				title={clock(op.startedAt)}
			>
				{timeAgo(op.startedAt)}
			</span>
		</Link>
	);
}

export function ConnectionLabel({
	conn,
	sub = true,
}: {
	conn: Connection;
	sub?: boolean;
}) {
	return (
		<div className="flex min-w-0 items-center gap-3">
			<ProviderLogo provider={conn.provider} size={28} />
			<div className="grid min-w-0">
				<span className="flex items-center gap-2 truncate font-medium">
					{conn.customer.orgName}
					{conn.sandbox ? <Badge tone="accent">Sandbox</Badge> : null}
				</span>
				{sub ? (
					<span className="text-muted-foreground truncate text-xs">
						{getProvider(conn.provider)?.name} · {conn.customer.email}
					</span>
				) : null}
			</div>
		</div>
	);
}
