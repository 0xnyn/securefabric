"use client";

import { unwrap } from "@securefabric/client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { PageBody, PageHeader } from "@/components/common";
import {
	JsonBlock,
	Pager,
	QueryState,
	StatusBadge,
	useCursorStack,
	When,
} from "@/components/kit";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Dialog, Select, SheetContent } from "@/components/ui/overlay";
import { Card, Table, Td, Th, Tr } from "@/components/ui/primitives";
import { OP_TONES } from "@/lib/types";
import { LogLines } from "./connection";

const ANY = "any";
const KINDS = [
	"sync",
	"auth",
	"action",
	"webhook_in",
	"webhook_out",
	"passthrough",
];

/** The operation log (OBS-01/02): one row per sync, verification, webhook or action, with its lines. */
export function LogsView() {
	const { client, env } = useEnv();
	const href = useHref();
	const pages = useCursorStack();
	const [kind, setKind] = useState(ANY);
	const [status, setStatus] = useState(ANY);
	const [open, setOpen] = useState<string | null>(null);
	const ops = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/operations", {
					params: {
						query: {
							cursor: pages.cursor,
							kind: kind === ANY ? undefined : kind,
							limit: 50,
							status: status === ANY ? undefined : status,
						},
					},
				})
			),
		queryKey: ["operations", env.id, kind, status, pages.cursor],
		refetchInterval: pages.page === 1 ? 10_000 : false,
	});
	const detail = useQuery({
		enabled: open !== null,
		queryFn: () =>
			unwrap(
				client.GET("/v1/operations/{operation_id}", {
					params: { path: { operation_id: open ?? "" } },
				})
			),
		queryKey: ["operation", env.id, open],
	});
	const filter = (fn: (v: string) => void) => (v: string) => {
		pages.reset();
		fn(v);
	};
	return (
		<>
			<PageHeader
				description="Every sync, auth check, webhook in or out, passthrough call and write-back action, with its request log."
				title="Logs"
			/>
			<PageBody className="grid gap-3">
				<div className="flex flex-wrap gap-2">
					<Select
						ariaLabel="Kind"
						className="w-36"
						onChange={filter(setKind)}
						options={[
							{ label: "Any kind", value: ANY },
							...KINDS.map((k) => ({ label: k, value: k })),
						]}
						size="sm"
						value={kind}
					/>
					<Select
						ariaLabel="Status"
						className="w-36"
						onChange={filter(setStatus)}
						options={[
							{ label: "Any status", value: ANY },
							...Object.keys(OP_TONES).map((k) => ({ label: k, value: k })),
						]}
						size="sm"
						value={status}
					/>
				</div>
				<QueryState
					empty={{
						description: "Operations appear as connections sync.",
						title: "No operations",
						when: (ops.data?.items.length ?? 0) === 0,
					}}
					query={ops}
				>
					<Card>
						<Table>
							<thead>
								<Tr>
									<Th>Started</Th>
									<Th>Kind</Th>
									<Th>Action</Th>
									<Th>Status</Th>
									<Th>Connection</Th>
									<Th className="text-right">Duration</Th>
									<Th className="text-right">Lines</Th>
								</Tr>
							</thead>
							<tbody>
								{ops.data?.items.map((o) => (
									<Tr
										className="hover:bg-muted/40 cursor-pointer"
										key={o.id}
										onClick={() => setOpen(o.id)}
									>
										<Td>
											<When value={o.started_at} />
										</Td>
										<Td className="text-xs">{o.kind}</Td>
										<Td className="text-xs">{o.action}</Td>
										<Td>
											<StatusBadge tones={OP_TONES} value={o.status} />
										</Td>
										<Td className="font-mono text-xs">
											{o.connection_id ? (
												<Link
													className="hover:underline"
													href={href(`/connections/${o.connection_id}`)}
													onClick={(e) => e.stopPropagation()}
												>
													{o.connection_id.slice(0, 8)}
												</Link>
											) : (
												"—"
											)}
										</Td>
										<Td className="text-right tabular-nums">
											{o.duration_ms === null ? "—" : `${o.duration_ms} ms`}
										</Td>
										<Td className="text-right tabular-nums">{o.line_count}</Td>
									</Tr>
								))}
							</tbody>
						</Table>
					</Card>
					<Pager
						count={ops.data?.items.length}
						hasNext={Boolean(ops.data?.next_cursor)}
						onNext={() => pages.next(ops.data?.next_cursor)}
						onPrev={pages.prev}
						page={pages.page}
					/>
				</QueryState>
			</PageBody>
			<Dialog
				onOpenChange={(o) => (o ? null : setOpen(null))}
				open={open !== null}
			>
				{open ? (
					<SheetContent
						description={<span className="font-mono text-xs">{open}</span>}
						title={
							detail.data
								? `${detail.data.kind} · ${detail.data.action}`
								: "Operation"
						}
					>
						<div className="grid gap-4 p-6">
							<QueryState query={detail}>
								{detail.data ? (
									<>
										{detail.data.job_id ? (
											<Link
												className="text-sm hover:underline"
												href={href(`/jobs/${detail.data.job_id}`)}
											>
												Open job {detail.data.job_id.slice(0, 8)}
											</Link>
										) : null}
										{detail.data.request_id ? (
											<p className="text-muted-foreground text-xs">
												Request {detail.data.request_id}
											</p>
										) : null}
										<JsonBlock value={detail.data.summary} />
										<LogLines
											lines={detail.data.lines.map((l) => ({
												...l,
												stream: null,
											}))}
										/>
									</>
								) : null}
							</QueryState>
						</div>
					</SheetContent>
				) : null}
			</Dialog>
		</>
	);
}
