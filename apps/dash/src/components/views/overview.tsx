"use client";

import { unwrap } from "@securefabric/client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { BarList, DonutChart, StackedBarChart } from "@/components/charts";
import { PageBody, PageHeader } from "@/components/common";
import {
	HealthBadge,
	QueryState,
	Section,
	SeverityLabel,
	StatusBadge,
	When,
} from "@/components/kit";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { Card, Table, Td, Th, Tr } from "@/components/ui/primitives";
import { compact, num } from "@/lib/format";
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

export function Stat({
	label,
	value,
	hint,
}: {
	label: string;
	value: React.ReactNode;
	hint?: React.ReactNode;
}) {
	return (
		<Card className="grid gap-1 p-4">
			<span className="text-muted-foreground text-xs">{label}</span>
			<span className="text-2xl font-semibold tabular-nums">{value}</span>
			{hint ? (
				<span className="text-muted-foreground text-xs">{hint}</span>
			) : null}
		</Card>
	);
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
	return (
		<>
			<PageHeader
				actions={
					<Button
						render={<Link href={href("/connections?new=1")} />}
						variant="primary"
					>
						Add connection
					</Button>
				}
				description="Connection health, data freshness, findings and recent syncs in this environment."
				title={env.name}
			/>
			<PageBody className="grid gap-8">
				<div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
					<Stat
						hint={`${num(live.unhealthy_connections ?? 0)} unhealthy`}
						label="Active connections"
						value={num(live.active_connections ?? 0)}
					/>
					<Stat
						label="Records stored"
						value={compact(live.records_stored ?? 0)}
					/>
					<Stat
						hint={`${num(live.failed_jobs_24h ?? 0)} failed`}
						label="Jobs (24h)"
						value={num(live.jobs_24h ?? 0)}
					/>
					<Stat
						label="API calls (24h)"
						value={compact(live.api_calls_24h ?? 0)}
					/>
					<Stat
						hint="across organizations"
						label="Findings"
						value={summary.data ? compact(summary.data.total) : "—"}
					/>
				</div>
				<div className="grid gap-6 lg:grid-cols-2">
					<Section title="Connections by health">
						<Card className="p-5">
							<QueryState query={connections} rows={2}>
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
							<QueryState query={summary} rows={2}>
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
						description="Connections that need someone to act"
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
								All logs
							</Button>
						}
						title="Recent syncs"
					>
						<Card>
							<QueryState query={ops} rows={3}>
								<Table>
									<thead>
										<Tr>
											<Th>Action</Th>
											<Th>Status</Th>
											<Th>Started</Th>
										</Tr>
									</thead>
									<tbody>
										{ops.data?.items.map((o) => (
											<Tr key={o.id}>
												<Td className="text-xs">
													{o.job_id ? (
														<Link
															className="hover:underline"
															href={href(`/jobs/${o.job_id}`)}
														>
															{o.action}
														</Link>
													) : (
														o.action
													)}
												</Td>
												<Td>
													<StatusBadge tones={OP_TONES} value={o.status} />
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
