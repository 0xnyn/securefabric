"use client";

import { unwrap } from "@securefabric/client";
import { Badge } from "@securefabric/ui/components/badge";
import { Button } from "@securefabric/ui/components/button";
import { Card } from "@securefabric/ui/components/card";
import { EmptyState } from "@securefabric/ui/components/empty-state";
import { Table, Td, Th, Tr } from "@securefabric/ui/components/table";
import { compact, num } from "@securefabric/ui/lib/format";
import {
	BarList,
	DonutChart,
	StackedBarChart,
} from "@securefabric/ui/patterns/charts";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { Section } from "@securefabric/ui/patterns/section";
import { Stat } from "@securefabric/ui/patterns/stat";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Gated } from "@/components/domain/access";
import { HealthBadge, SeverityLabel } from "@/components/domain/badges";
import { QueryState } from "@/components/domain/query-state";
import { When } from "@/components/domain/when";
import { useEnv, useHref } from "@/components/shell/env-context";
import { humanize, syncActionLabel } from "@/lib/labels";
import { HEALTH, OP_TONES, SEVERITIES } from "@/lib/types";

const TONE_COLOR: Record<string, string> = {
	busy: "var(--ds-accent)",
	error: "var(--ds-warn)",
	neutral: "var(--muted-foreground)",
	ok: "var(--ds-ok, #22c55e)",
	warn: "var(--ds-severity-medium, #f59e0b)",
};

export function useUsage(days = 30) {
	const { client, env } = useEnv();
	return useQuery({
		queryFn: () =>
			unwrap(client.GET("/v1/usage", { params: { query: { days } } })),
		queryKey: ["usage", env.id, days],
		refetchInterval: 30_000,
	});
}

export function OverviewView() {
	const { client, env } = useEnv();
	const href = useHref();
	const usage = useUsage(14);
	const connections = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/connections", { params: { query: { limit: 500 } } })
			),
		queryKey: ["connections", env.id, "overview"],
		refetchInterval: 30_000,
	});
	const orgs = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/organizations", { params: { query: { limit: 500 } } })
			),
		queryKey: ["organizations", env.id, "all"],
	});
	const ops = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/operations", {
					params: { query: { kind: "sync", limit: 10 } },
				})
			),
		queryKey: ["operations", env.id, "overview"],
		refetchInterval: 15_000,
	});
	// Finding counts are per organization (API-03); sum the first page of organizations.
	const orgIds = (orgs.data?.items ?? []).slice(0, 25).map((o) => o.id);
	const summary = useQuery({
		enabled: orgs.isSuccess,
		queryFn: async () => {
			const all = await Promise.all(
				orgIds.map((id) =>
					unwrap(
						client.GET("/v1/vulnerability_findings/summary", {
							params: { header: { "X-ORGANIZATION-ID": id } },
						})
					)
				)
			);
			const open: Record<string, number> = {};
			let total = 0;
			for (const s of all) {
				total += s.total;
				for (const [k, v] of Object.entries(s.open_by_severity)) {
					open[k] = (open[k] ?? 0) + v;
				}
			}
			return { open, total };
		},
		queryKey: ["findings-summary", env.id, orgIds.join(",")],
	});
	const live = (usage.data?.live ?? {}) as Partial<Record<string, number>>;
	const byHealth = new Map<string, number>();
	for (const c of connections.data?.items ?? []) {
		byHealth.set(c.health.name, (byHealth.get(c.health.name) ?? 0) + 1);
	}
	const unhealthy = (connections.data?.items ?? []).filter(
		(c) => c.health.name !== "HEALTHY" && c.state !== "DELETED"
	);
	const hours = (usage.data?.api_calls_by_hour ?? []) as {
		hour: string;
		api_calls: number;
	}[];
	const noConnections =
		connections.isSuccess && connections.data.items.length === 0;
	const openFindings = Object.values(summary.data?.open ?? {}).reduce(
		(a, b) => a + b,
		0
	);
	const addConnection = (size?: "sm") => (
		<Gated requires={{ scope: "provisioning:write" }}>
			<Button
				render={<Link href={href("/connections?new=1")} />}
				size={size}
				variant="primary"
			>
				Add connection
			</Button>
		</Gated>
	);
	return (
		<>
			<PageHeader
				actions={addConnection()}
				description="How your connections, findings and syncs are doing in this environment."
				title={env.name}
			/>
			<PageBody className="grid gap-8">
				{noConnections ? (
					<EmptyState
						action={
							<div className="flex flex-wrap justify-center gap-2">
								{addConnection("sm")}
								<Button
									render={<Link href={href("/catalog")} />}
									size="sm"
									variant="outline"
								>
									Browse the catalog
								</Button>
							</div>
						}
						description="Connect a customer's security tool to start syncing their findings and resources."
						title="No connections yet"
					/>
				) : null}
				<StatTiles findings={summary.data?.total} live={live} />
				<div className="grid gap-6 lg:grid-cols-2">
					<Section title="Connections by health">
						<Card className="p-5">
							<QueryState
								empty={{
									description: "Health shows here once you add a connection.",
									title: "No connections yet",
									when: (connections.data?.items.length ?? 0) === 0,
								}}
								query={connections}
								rows={2}
							>
								<DonutChart
									ariaLabel="Connections by health"
									slices={[...byHealth.entries()].map(([k, v]) => ({
										color:
											TONE_COLOR[HEALTH[k]?.tone ?? "neutral"] ??
											"var(--muted-foreground)",
										key: k,
										label: HEALTH[k]?.label ?? k,
										value: v,
									}))}
									total={connections.data?.items.length ?? 0}
									totalLabel="connections"
								/>
							</QueryState>
						</Card>
					</Section>
					<Section title="Open findings by severity">
						<Card className="p-5">
							<QueryState
								empty={{
									description: noConnections
										? "Findings show here once a connection finishes its first sync."
										: "Nothing open right now. New findings show here after each sync.",
									title: "No open findings",
									when: openFindings === 0,
								}}
								query={summary}
								rows={2}
							>
								<BarList
									items={SEVERITIES.map((s) => ({
										key: s,
										label: <SeverityLabel value={s} />,
										value: summary.data?.open[s] ?? 0,
									}))}
								/>
							</QueryState>
						</Card>
					</Section>
				</div>
				{unhealthy.length ? (
					<Section
						description="Connections that aren't healthy, and why."
						title="Needs attention"
					>
						<Card>
							<Table>
								<tbody>
									{unhealthy.slice(0, 8).map((c) => (
										<Tr key={c.id}>
											<Td>
												<Link
													className="font-medium hover:underline"
													href={href(`/connections/${c.id}`)}
												>
													{c.identifier ?? c.vendor}{" "}
													<span className="text-muted-foreground font-mono text-xs">
														{c.id.slice(0, 8)}
													</span>
												</Link>
											</Td>
											<Td>
												<HealthBadge health={c.health} />
											</Td>
											<Td className="text-muted-foreground max-w-md truncate text-xs">
												{c.health.description}
											</Td>
										</Tr>
									))}
								</tbody>
							</Table>
						</Card>
					</Section>
				) : null}
				<div className="grid gap-6 lg:grid-cols-2">
					<Section title="API calls, last 24 hours">
						<Card className="p-5">
							<StackedBarChart
								ariaLabel="API calls per hour"
								data={hours.map((h) => ({
									api_calls: h.api_calls,
									label: new Date(h.hour).toLocaleTimeString("en-US", {
										hour: "numeric",
									}),
								}))}
								series={[
									{
										color: "var(--ds-accent)",
										key: "api_calls",
										label: "API calls",
									},
								]}
							/>
						</Card>
					</Section>
					<Section
						action={
							<Button
								render={<Link href={href("/logs")} />}
								size="sm"
								variant="ghost"
							>
								View all logs
							</Button>
						}
						title="Recent syncs"
					>
						<Card>
							<QueryState
								empty={{
									description: noConnections
										? "Syncs show here once you add a connection."
										: "Syncs show here as soon as one starts.",
									title: "No syncs yet",
									when: (ops.data?.items.length ?? 0) === 0,
								}}
								query={ops}
								rows={3}
							>
								<Table>
									<thead>
										<Tr>
											<Th>Sync</Th>
											<Th>Status</Th>
											<Th>Started</Th>
										</Tr>
									</thead>
									<tbody>
										{ops.data?.items.map((o) => (
											<Tr key={o.id}>
												<Td>
													{o.job_id ? (
														<Link
															className="hover:underline"
															href={href(`/jobs/${o.job_id}`)}
														>
															{syncActionLabel(o.action)}
														</Link>
													) : (
														syncActionLabel(o.action)
													)}
												</Td>
												<Td>
													<Badge tone={OP_TONES[o.status] ?? "neutral"}>
														{humanize(o.status)}
													</Badge>
												</Td>
												<Td>
													<When value={o.started_at} />
												</Td>
											</Tr>
										))}
									</tbody>
								</Table>
							</QueryState>
						</Card>
					</Section>
				</div>
			</PageBody>
		</>
	);
}

function StatTiles({
	live,
	findings,
}: {
	live: Partial<Record<string, number>>;
	findings: number | undefined;
}) {
	const unhealthy = live.unhealthy_connections ?? 0;
	const failed = live.failed_jobs_24h ?? 0;
	return (
		<div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
			<Stat
				hint={unhealthy ? `${num(unhealthy)} need attention` : "All healthy"}
				label="Active connections"
				value={num(live.active_connections ?? 0)}
			/>
			<Stat label="Records stored" value={compact(live.records_stored ?? 0)} />
			<Stat
				hint={failed ? `${num(failed)} failed` : "None failed"}
				label="Jobs, last 24 hours"
				value={num(live.jobs_24h ?? 0)}
			/>
			<Stat
				label="API calls, last 24 hours"
				value={compact(live.api_calls_24h ?? 0)}
			/>
			<Stat
				hint="Across your organizations"
				label="Findings"
				value={findings === undefined ? "—" : compact(findings)}
			/>
		</div>
	);
}
