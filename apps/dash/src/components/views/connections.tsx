"use client";

import { unwrap } from "@securefabric/client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { PageBody, PageHeader } from "@/components/common";
import {
	ConnectorLogo,
	HealthBadge,
	Pager,
	QueryState,
	StatusBadge,
	useCursorStack,
	When,
} from "@/components/kit";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/overlay";
import { Card, Table, Td, Th, Tr } from "@/components/ui/primitives";
import { HEALTH, STATE_TONES } from "@/lib/types";
import { AddConnectionDialog } from "./add-connection";

const ALL = "all";

/** The connection table, optionally for one organization (CON-13 filters). */
export function ConnectionsTable({
	organizationId,
}: {
	organizationId?: string;
}) {
	const { client, env } = useEnv();
	const href = useHref();
	const pages = useCursorStack();
	const [vendor, setVendor] = useState(ALL);
	const [state, setState] = useState(ALL);
	const [health, setHealth] = useState(ALL);
	const connections = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/connections", {
					params: {
						query: {
							cursor: pages.cursor,
							healthStatusCodes: health === ALL ? undefined : health,
							limit: 50,
							organizationId,
							state: state === ALL ? undefined : state,
							vendor: vendor === ALL ? undefined : vendor,
						},
					},
				})
			),
		queryKey: [
			"connections",
			env.id,
			organizationId,
			vendor,
			state,
			health,
			pages.cursor,
		],
	});
	const orgs = useQuery({
		enabled: !organizationId,
		queryFn: () =>
			unwrap(
				client.GET("/v1/organizations", { params: { query: { limit: 500 } } })
			),
		queryKey: ["organizations", env.id, "all"],
	});
	const orgName = new Map((orgs.data?.items ?? []).map((o) => [o.id, o.name]));
	const reset =
		<T,>(fn: (v: T) => void) =>
		(v: T) => {
			pages.reset();
			fn(v);
		};
	return (
		<div className="grid gap-3">
			<div className="flex flex-wrap gap-2">
				<Select
					ariaLabel="Vendor"
					className="w-40"
					onChange={reset(setVendor)}
					options={[
						{ label: "All vendors", value: ALL },
						{ label: "GitHub", value: "GITHUB" },
						{ label: "Sandbox", value: "SANDBOX" },
					]}
					size="sm"
					value={vendor}
				/>
				<Select
					ariaLabel="State"
					className="w-40"
					onChange={reset(setState)}
					options={[ALL, "PENDING", "ACTIVE", "PAUSED", "DELETED"].map((s) => ({
						label: s === ALL ? "All states" : s.toLowerCase(),
						value: s,
					}))}
					size="sm"
					value={state}
				/>
				<Select
					ariaLabel="Health"
					className="w-48"
					onChange={reset(setHealth)}
					options={[
						{ label: "Any health", value: ALL },
						...Object.entries(HEALTH).map(([k, v]) => ({
							label: v.label,
							value: k,
						})),
					]}
					size="sm"
					value={health}
				/>
			</div>
			<QueryState
				empty={{
					description:
						"Add a connection, or send your customer a connect link.",
					title: "No connections",
					when: (connections.data?.items.length ?? 0) === 0,
				}}
				query={connections}
			>
				<Card>
					<Table>
						<thead>
							<Tr>
								<Th>Connection</Th>
								{organizationId ? null : <Th>Organization</Th>}
								<Th>State</Th>
								<Th>Health</Th>
								<Th>Updated</Th>
							</Tr>
						</thead>
						<tbody>
							{connections.data?.items.map((c) => (
								<Tr className="hover:bg-muted/40" key={c.id}>
									<Td>
										<Link
											className="flex items-center gap-3"
											href={href(`/connections/${c.id}`)}
										>
											<ConnectorLogo id={c.vendor} />
											<span className="grid">
												<span className="font-medium">
													{c.identifier ?? c.vendor}
												</span>
												<span className="text-muted-foreground font-mono text-xs">
													{c.id.slice(0, 8)}
												</span>
											</span>
											{c.is_sandbox ? (
												<span className="text-muted-foreground text-xs">
													sandbox
												</span>
											) : null}
										</Link>
									</Td>
									{organizationId ? null : (
										<Td>
											<Link
												className="hover:underline"
												href={href(`/organizations/${c.organization_id}`)}
											>
												{orgName.get(c.organization_id) ??
													c.organization_id.slice(0, 8)}
											</Link>
										</Td>
									)}
									<Td>
										<StatusBadge tones={STATE_TONES} value={c.state} />
									</Td>
									<Td>
										<HealthBadge health={c.health} />
									</Td>
									<Td>
										<When value={c.updated_at} />
									</Td>
								</Tr>
							))}
						</tbody>
					</Table>
				</Card>
				<Pager
					count={connections.data?.items.length}
					hasNext={Boolean(connections.data?.next_cursor)}
					onNext={() => pages.next(connections.data?.next_cursor)}
					onPrev={pages.prev}
					page={pages.page}
				/>
			</QueryState>
		</div>
	);
}

export function ConnectionsView() {
	const params = useSearchParams();
	const [open, setOpen] = useState(params.get("new") === "1");
	return (
		<>
			<PageHeader
				actions={
					<Button onClick={() => setOpen(true)} variant="primary">
						Add connection
					</Button>
				}
				description="One vendor tenant each: its health, what it can read, and when it last synced."
				title="Connections"
			/>
			<PageBody>
				<ConnectionsTable />
			</PageBody>
			<AddConnectionDialog onOpenChange={setOpen} open={open} />
		</>
	);
}
