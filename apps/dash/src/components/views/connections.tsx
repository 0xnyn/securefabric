"use client";

import { unwrap } from "@securefabric/client";
import { Badge, type Tone } from "@securefabric/ui/components/badge";
import { Button } from "@securefabric/ui/components/button";
import { Card } from "@securefabric/ui/components/card";
import { Select } from "@securefabric/ui/components/select";
import { Table, Td, Th, Tr } from "@securefabric/ui/components/table";
import { EntityAvatar } from "@securefabric/ui/patterns/avatar";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { useQuery } from "@tanstack/react-query";
import { PlusIcon } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Gated } from "@/components/domain/access";
import { HealthBadge } from "@/components/domain/badges";
import { ConnectorLogo } from "@/components/domain/connector-logo";
import { Pager, useCursorStack } from "@/components/domain/pager";
import { QueryState } from "@/components/domain/query-state";
import { When } from "@/components/domain/when";
import { useAccess, useEnv, useHref } from "@/components/shell/env-context";
import { api } from "@/lib/api";
import { HEALTH, STATE_TONES } from "@/lib/types";
import { AddConnectionDialog } from "./add-connection";

const ALL = "all";

/** Connection states (schema ConnectionState), in words. */
export const STATE_LABELS: Record<string, string> = {
	ACTIVE: "Active",
	DELETED: "Deleted",
	HARD_DELETED: "Purged",
	PAUSED: "Paused",
	PENDING: "Pending",
};

/** "RETRY_WAIT" → "Retry wait", for enums without a better word. */
export function sentence(value: string): string {
	const s = value.replaceAll("_", " ").toLowerCase();
	return s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * A status badge in words: "Active", "Not enabled". Like kit's StatusBadge,
 * with a label map and sentence case instead of the lowercased enum.
 */
export function EnumBadge({
	value,
	tones,
	labels = {},
}: {
	value: string | null | undefined;
	tones: Record<string, Tone>;
	labels?: Record<string, string>;
}) {
	if (!value) {
		return <span className="text-muted-foreground">—</span>;
	}
	return (
		<Badge tone={tones[value] ?? "neutral"}>
			{labels[value] ?? sentence(value)}
		</Badge>
	);
}

export interface ConnectorInfo {
	logo: string | null;
	name: string;
}

/**
 * The public connector catalogue as id → name and logo, so a connection reads
 * "GitHub" rather than `GITHUB`. Shares its cache with the catalog page.
 */
export function useConnectorInfo(): (id: string) => ConnectorInfo {
	const connectors = useQuery({
		queryFn: () => unwrap(api.GET("/v1/connectors")),
		queryKey: ["connectors"],
		staleTime: 5 * 60_000,
	});
	const byId = new Map(
		(connectors.data ?? []).map((c) => [
			c.id,
			{ logo: c.logo_url, name: c.name },
		])
	);
	return (id) => byId.get(id) ?? { logo: null, name: id };
}

/** The connection table, optionally for one organization (CON-13 filters). */
export function ConnectionsTable({
	organizationId,
	onAdd,
}: {
	organizationId?: string;
	/** Opens the add-connection dialog, for the empty state's action. */
	onAdd?: () => void;
}) {
	const { client, env } = useEnv();
	const href = useHref();
	const pages = useCursorStack();
	const connector = useConnectorInfo();
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
	const filtered = vendor !== ALL || state !== ALL || health !== ALL;
	const clearFilters = () => {
		pages.reset();
		setVendor(ALL);
		setState(ALL);
		setHealth(ALL);
	};
	return (
		<div className="grid gap-3">
			<div className="flex flex-wrap items-center gap-2">
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
						label: s === ALL ? "All states" : (STATE_LABELS[s] ?? s),
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
				{filtered ? (
					<Button onClick={clearFilters} size="sm" variant="ghost">
						Clear filters
					</Button>
				) : null}
			</div>
			<QueryState
				empty={
					filtered
						? {
								action: (
									<Button onClick={clearFilters} size="sm" variant="outline">
										Clear filters
									</Button>
								),
								description: "Clear the filters to see every connection.",
								title: "No matching connections",
								when: (connections.data?.items.length ?? 0) === 0,
							}
						: {
								action: onAdd ? (
									<Gated requires={{ scope: "provisioning:write" }}>
										<Button onClick={onAdd} size="sm" variant="primary">
											<PlusIcon /> Add connection
										</Button>
									</Gated>
								) : undefined,
								description: organizationId
									? "Add a connection, or send this organization a connect link to set it up."
									: "Connections you add or customers set up through a connect link appear here.",
								title: "No connections yet",
								when: (connections.data?.items.length ?? 0) === 0,
							}
				}
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
							{connections.data?.items.map((c) => {
								const info = connector(c.vendor);
								return (
									<Tr className="hover:bg-muted/40" key={c.id}>
										<Td>
											<Link
												className="flex items-center gap-3"
												href={href(`/connections/${c.id}`)}
											>
												<ConnectorLogo
													id={c.vendor}
													logo={info.logo}
													name={info.name}
												/>
												<span className="grid">
													<span className="font-medium">
														{c.identifier ?? info.name}
													</span>
													<span className="text-muted-foreground text-xs">
														{info.name} ·{" "}
														<span className="font-mono">
															{c.id.slice(0, 8)}
														</span>
													</span>
												</span>
												{c.is_sandbox ? <Badge>Sandbox</Badge> : null}
											</Link>
										</Td>
										{organizationId ? null : (
											<Td>
												<Link
													className="inline-flex items-center gap-2 hover:underline"
													href={href(`/organizations/${c.organization_id}`)}
												>
													<EntityAvatar
														name={
															orgName.get(c.organization_id) ?? "Organization"
														}
														size={20}
													/>
													{orgName.get(c.organization_id) ?? (
														<span className="font-mono text-xs">
															{c.organization_id.slice(0, 8)}
														</span>
													)}
												</Link>
											</Td>
										)}
										<Td>
											<EnumBadge
												labels={STATE_LABELS}
												tones={STATE_TONES}
												value={c.state}
											/>
										</Td>
										<Td>
											<HealthBadge health={c.health} />
										</Td>
										<Td>
											<When value={c.updated_at} />
										</Td>
									</Tr>
								);
							})}
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
	const access = useAccess();
	const [open, setOpen] = useState(
		params.get("new") === "1" && access.can("provisioning:write")
	);
	return (
		<>
			<PageHeader
				actions={
					<Gated requires={{ scope: "provisioning:write" }}>
						<Button onClick={() => setOpen(true)} variant="primary">
							<PlusIcon /> Add connection
						</Button>
					</Gated>
				}
				description="Your customers' vendor connections, their health and last sync."
				title="Connections"
			/>
			<PageBody>
				<ConnectionsTable onAdd={() => setOpen(true)} />
			</PageBody>
			<AddConnectionDialog onOpenChange={setOpen} open={open} />
		</>
	);
}
