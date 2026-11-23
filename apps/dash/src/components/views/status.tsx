"use client";

import { type schemas, unwrap } from "@securefabric/client";
import { Button } from "@securefabric/ui/components/button";
import { Card } from "@securefabric/ui/components/card";
import { EmptyState } from "@securefabric/ui/components/empty-state";
import { Table, Td, Th, Tr } from "@securefabric/ui/components/table";
import { duration, num } from "@securefabric/ui/lib/format";
import { cn } from "@securefabric/ui/lib/utils";
import { DonutChart, StackedBarChart } from "@securefabric/ui/patterns/charts";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { Section } from "@securefabric/ui/patterns/section";
import { Stat } from "@securefabric/ui/patterns/stat";
import { type UseQueryResult, useQuery } from "@tanstack/react-query";
import { CableIcon, CircleCheckIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { QueryState } from "@/components/domain/query-state";
import { When } from "@/components/domain/when";
import { useAccess, useEnv, useHref } from "@/components/shell/env-context";
import { humanize } from "@/lib/labels";
import { HEALTH } from "@/lib/types";

/*
 * Status, for the people using SecureFabric rather than running it: is it
 * working, are my syncs keeping up, and if not, what's affected. Laid out like
 * Metrics — stat tiles, then titled cards holding a chart or a table — from
 * GET /v1/status and this environment's connections. Raw worker, queue and
 * run facts are under "Technical details", for admins and operators.
 */

type SystemStatus = schemas["SystemStatus"];

type Level = "ok" | "degraded" | "down" | "unknown";

const LEVELS: Record<Level, { dot: string; label: string; summary: string }> = {
	degraded: {
		dot: "bg-ds-severity-medium",
		label: "Degraded",
		summary: "Some services are degraded",
	},
	down: {
		dot: "bg-destructive",
		label: "Down",
		summary: "Some services are down",
	},
	ok: {
		dot: "bg-ds-success",
		label: "Operational",
		summary: "All services operational",
	},
	unknown: {
		dot: "bg-muted-foreground/40",
		label: "Checking",
		summary: "Checking services…",
	},
};

/** The API's problem strings (domain/status.py), in words a customer can act on. */
function explain(problem: string): string {
	if (problem.startsWith("no worker online")) {
		return "Syncs are paused because no sync workers are running. They resume once workers are back.";
	}
	if (problem.startsWith("queue lag")) {
		return "Syncs are waiting longer than usual to start. Your data may be a few minutes behind.";
	}
	if (problem.includes("RUNNING for over 15 minutes")) {
		return "Some syncs have run for over 15 minutes. We retry them automatically.";
	}
	if (problem.includes("paging alert")) {
		return "We're investigating an incident.";
	}
	if (problem.includes("migration")) {
		return "We're applying an update. Some pages may be slow for a few minutes.";
	}
	if (problem.includes("database unreachable")) {
		return "We can't reach the data store, so nothing can be read or synced right now.";
	}
	return problem;
}

function LevelLabel({ level, label }: { level: Level; label?: string }) {
	return (
		<span className="inline-flex items-center gap-2">
			<span className={cn("size-2 rounded-full", LEVELS[level].dot)} />
			{label ?? LEVELS[level].label}
		</span>
	);
}

// ---------------------------------------------------------------------------
// Response time, measured from this browser while the page is open.

interface Probe {
	at: number;
	ms: number | null;
}

const PROBES = 30;

function useProbes(
	checkedAt: string | undefined,
	startedAt: number | null
): Probe[] {
	const [probes, setProbes] = useState<Probe[]>([]);
	const last = useRef<string | undefined>(undefined);
	useEffect(() => {
		if (checkedAt === undefined || checkedAt === last.current) {
			return;
		}
		last.current = checkedAt;
		const ms =
			startedAt === null ? null : Math.round(performance.now() - startedAt);
		setProbes((p) => [...p.slice(-(PROBES - 1)), { at: Date.now(), ms }]);
	}, [checkedAt, startedAt]);
	return probes;
}

// ---------------------------------------------------------------------------
// Services

interface Service {
	detail: string;
	level: Level;
	name: string;
}

interface Queue {
	name: string;
	oldest_pending_seconds?: number | null;
	pending?: number;
}

const SERVICE_NAMES = [
	"API",
	"Data store",
	"Sync engine",
	"Sync queue",
	"Webhooks",
	"Connect page",
];

function lagged(seconds: number): Level {
	return seconds > 60 ? "degraded" : "ok";
}

function oldestWait(queues: Queue[]): number {
	return Math.max(0, ...queues.map((q) => q.oldest_pending_seconds ?? 0));
}

/** The services a customer depends on, from the system facts. */
function services(
	s: SystemStatus | undefined,
	unreachable: boolean,
	lastProbeMs: number | null
): Service[] {
	if (unreachable || !s) {
		const level: Level = unreachable ? "down" : "unknown";
		return SERVICE_NAMES.map((name) => ({
			detail: unreachable && name === "API" ? "Not answering" : "—",
			level,
			name,
		}));
	}
	const db = s.database as { reachable?: boolean; latency_ms?: number };
	const online = s.workers.filter((w) => w.online).length;
	const queues = s.queues as unknown as Queue[];
	const worstLag = oldestWait(queues);
	const hooks = queues.find(
		(q) => q.name.includes("webhook") || q.name.includes("outbox")
	);
	const hookLag = hooks?.oldest_pending_seconds ?? 0;
	let engine: Level = "ok";
	if (s.workers.length > 0 && online === 0) {
		engine = "down";
	} else if (s.stuck_runs > 0) {
		engine = "degraded";
	}
	let dbDetail = "Unreachable";
	if (db.reachable) {
		dbDetail =
			db.latency_ms === undefined
				? "Reachable"
				: `Responds in ${Math.round(db.latency_ms)} ms`;
	}
	return [
		{
			detail:
				lastProbeMs === null ? "Answering" : `Answers in ${lastProbeMs} ms`,
			level: "ok",
			name: "API",
		},
		{
			detail: dbDetail,
			level: db.reachable ? "ok" : "down",
			name: "Data store",
		},
		{
			detail: s.workers.length
				? `${online} of ${s.workers.length} workers online`
				: "Running",
			level: engine,
			name: "Sync engine",
		},
		{
			detail:
				worstLag > 60
					? `Oldest sync waiting ${duration(worstLag * 1000)}`
					: "Syncs start on time",
			level: lagged(worstLag),
			name: "Sync queue",
		},
		{
			detail:
				hookLag > 60
					? `Deliveries delayed by ${duration(hookLag * 1000)}`
					: "Delivering on time",
			level: lagged(hookLag),
			name: "Webhooks",
		},
		{ detail: "Accepting connections", level: "ok", name: "Connect page" },
	];
}

// ---------------------------------------------------------------------------

export function StatusView() {
	const { client, me } = useEnv();
	const access = useAccess();
	const startedAt = useRef<number | null>(null);
	const status = useQuery({
		queryFn: async () => {
			startedAt.current = performance.now();
			try {
				return await unwrap(client.GET("/v1/status"));
			} catch (e) {
				startedAt.current = null;
				throw e;
			}
		},
		queryKey: ["status", me.actor_id],
		refetchInterval: 10_000,
	});
	const probes = useProbes(status.data?.checked_at, startedAt.current);
	const s = status.data;
	const level: Level = status.isError
		? "down"
		: ((s?.status as Level | undefined) ?? "unknown");
	const problems = status.isError
		? ["We can't reach the SecureFabric API from your browser."]
		: [...new Set((s?.problems ?? []).map(explain))];

	return (
		<>
			<PageHeader
				actions={
					<span className="text-muted-foreground inline-flex items-center gap-2 text-sm">
						<span className={cn("size-2 rounded-full", LEVELS[level].dot)} />
						{LEVELS[level].summary}
					</span>
				}
				description="Whether SecureFabric and your syncs are running normally. Updates every 10 seconds."
				title="Status"
			/>
			<PageBody className="grid gap-8">
				{problems.length ? (
					<Card className="border-ds-severity-medium/40 grid gap-1 p-5">
						<span className="text-sm font-medium">What's affected</span>
						<ul className="text-muted-foreground grid list-disc gap-1 pl-5 text-sm">
							{problems.map((p) => (
								<li key={p}>{p}</li>
							))}
						</ul>
					</Card>
				) : null}
				<StatTiles probes={probes} status={s} />
				<div className="grid gap-6 lg:grid-cols-2">
					<Section
						description="The parts of SecureFabric your integration depends on."
						title="Services"
					>
						<Card>
							<Table>
								<thead>
									<Tr>
										<Th>Service</Th>
										<Th>Detail</Th>
										<Th className="text-right">State</Th>
									</Tr>
								</thead>
								<tbody>
									{services(s, status.isError, probes.at(-1)?.ms ?? null).map(
										(c) => (
											<Tr key={c.name}>
												<Td className="font-medium">{c.name}</Td>
												<Td className="text-muted-foreground">{c.detail}</Td>
												<Td className="text-right whitespace-nowrap">
													<LevelLabel level={c.level} />
												</Td>
											</Tr>
										)
									)}
								</tbody>
							</Table>
						</Card>
					</Section>
					<Section
						description={
							s ? (
								<>
									In milliseconds, from your browser. Last check{" "}
									<When value={s.checked_at} />.
								</>
							) : undefined
						}
						title="API response time"
					>
						<Card className="p-5">
							<StackedBarChart
								ariaLabel="API response time"
								data={probes.map((p) => ({
									label: new Date(p.at).toLocaleTimeString([], {
										hour: "2-digit",
										minute: "2-digit",
										second: "2-digit",
									}),
									ms: p.ms ?? 0,
								}))}
								formatValue={(n) => String(n)}
								series={[
									{
										color: "var(--ds-accent)",
										key: "ms",
										label: "Response time",
									},
								]}
							/>
						</Card>
					</Section>
				</div>
				{access.can("provisioning:read") ? <YourSyncs /> : null}
				{access.isAdmin || me.is_operator ? (
					<TechnicalDetails status={status} />
				) : null}
			</PageBody>
		</>
	);
}

function StatTiles({
	status: s,
	probes,
}: {
	status: SystemStatus | undefined;
	probes: Probe[];
}) {
	const measured = probes
		.map((p) => p.ms)
		.filter((ms): ms is number => ms !== null);
	const avg = measured.length
		? Math.round(measured.reduce((a, b) => a + b, 0) / measured.length)
		: null;
	const online = (s?.workers ?? []).filter((w) => w.online).length;
	const wait = oldestWait((s?.queues ?? []) as unknown as Queue[]);
	// Failed syncs come from this environment's usage, not the system-wide
	// count in /v1/status, which spans every account.
	const { client, env } = useEnv();
	const access = useAccess();
	const usage = useQuery({
		enabled: access.can("provisioning:read"),
		queryFn: () =>
			unwrap(client.GET("/v1/usage", { params: { query: { days: 1 } } })),
		queryKey: ["usage", env.id, 1],
		refetchInterval: 30_000,
	});
	const live = (usage.data?.live ?? {}) as Partial<Record<string, number>>;
	const failed = live.failed_jobs_24h ?? 0;
	const jobs = live.jobs_24h ?? 0;
	return (
		<div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
			<Stat
				hint="From your browser"
				label="API response time"
				value={avg === null ? "—" : `${avg} ms`}
			/>
			<Stat
				hint={s?.workers.length ? `of ${s.workers.length}` : undefined}
				label="Sync workers online"
				value={s ? num(online) : "—"}
			/>
			<Stat
				hint={wait > 60 ? "Longer than usual" : "Syncs start on time"}
				label="Oldest queued sync"
				value={wait ? duration(wait * 1000) : "No wait"}
			/>
			<Stat
				hint={
					jobs ? `of ${num(jobs)} in ${env.name}` : `None ran in ${env.name}`
				}
				label="Failed syncs, last 24 hours"
				value={num(failed)}
			/>
		</div>
	);
}

const HEALTH_COLOR: Record<string, string> = {
	busy: "var(--ds-accent)",
	error: "var(--ds-warn)",
	neutral: "var(--muted-foreground)",
	ok: "var(--ds-ok, #22c55e)",
	warn: "var(--ds-severity-medium, #f59e0b)",
};

/** This environment's connections, by health, and the ones that need a fix. */
function YourSyncs() {
	const { client, env } = useEnv();
	const href = useHref();
	const connections = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/connections", { params: { query: { limit: 500 } } })
			),
		queryKey: ["connections", env.id, "overview"],
		refetchInterval: 30_000,
	});
	const live = (connections.data?.items ?? []).filter(
		(c) => c.state !== "DELETED"
	);
	const byHealth = new Map<string, number>();
	for (const c of live) {
		byHealth.set(c.health.name, (byHealth.get(c.health.name) ?? 0) + 1);
	}
	const unhealthy = live.filter((c) => c.health.name !== "HEALTHY");
	return (
		<div className="grid gap-6 lg:grid-cols-2">
			<Section
				description={`Every connection in ${env.name}, by health.`}
				title="Connections"
			>
				<Card className="p-5">
					<QueryState
						empty={{
							description:
								"Connection health shows here once a customer connects a tool.",
							icon: <CableIcon className="size-4" />,
							title: "No connections yet",
							when: live.length === 0,
						}}
						query={connections}
						rows={2}
					>
						<DonutChart
							ariaLabel="Connections by health"
							slices={[...byHealth.entries()].map(([k, v]) => ({
								color:
									HEALTH_COLOR[HEALTH[k]?.tone ?? "neutral"] ??
									"var(--muted-foreground)",
								key: k,
								label: HEALTH[k]?.label ?? humanize(k),
								value: v,
							}))}
							total={live.length}
							totalLabel="connections"
						/>
					</QueryState>
				</Card>
			</Section>
			<Section
				description="Connections that aren't syncing, and who needs to fix them."
				title="Needs attention"
			>
				<Card>
					{unhealthy.length ? (
						<Table>
							<thead>
								<Tr>
									<Th>Connection</Th>
									<Th>Problem</Th>
									<Th className="text-right">Who fixes it</Th>
								</Tr>
							</thead>
							<tbody>
								{unhealthy.slice(0, 8).map((c) => (
									<Tr key={c.id}>
										<Td className="font-medium">
											<Link
												className="hover:underline"
												href={href(`/connections/${c.id}`)}
											>
												{c.identifier ?? c.vendor}
											</Link>
										</Td>
										<Td className="text-muted-foreground">
											{HEALTH[c.health.name]?.label ?? humanize(c.health.name)}
										</Td>
										<Td className="text-right">
											{HEALTH[c.health.name]?.owner || "—"}
										</Td>
									</Tr>
								))}
							</tbody>
						</Table>
					) : (
						<EmptyState
							description={
								live.length
									? "Every connection is syncing normally."
									: "Connections that stop syncing show here, with who needs to fix them."
							}
							icon={<CircleCheckIcon className="size-4" />}
							title="Nothing needs attention"
						/>
					)}
				</Card>
			</Section>
		</div>
	);
}

function DetailTable({
	headers,
	rows,
	empty,
}: {
	headers: string[];
	rows: React.ReactNode[][];
	empty: string;
}) {
	if (rows.length === 0) {
		return (
			<Card>
				<EmptyState description={empty} title="Nothing to show" />
			</Card>
		);
	}
	const last = headers.length - 1;
	return (
		<Card>
			<Table>
				<thead>
					<Tr>
						{headers.map((h, i) => (
							<Th className={i === last ? "text-right" : undefined} key={h}>
								{h}
							</Th>
						))}
					</Tr>
				</thead>
				<tbody>
					{rows.map((r, i) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: status rows have no stable id
						<Tr key={i}>
							{r.map((cell, j) => (
								<Td
									className={j === last ? "text-right tabular-nums" : undefined}
									// biome-ignore lint/suspicious/noArrayIndexKey: fixed columns
									key={j}
								>
									{cell}
								</Td>
							))}
						</Tr>
					))}
				</tbody>
			</Table>
		</Card>
	);
}

function TechnicalDetails({
	status,
}: {
	status: UseQueryResult<SystemStatus>;
}) {
	const [open, setOpen] = useState(false);
	const s = status.data;
	return (
		<Section
			action={
				<Button onClick={() => setOpen(!open)} size="sm">
					{open ? "Hide details" : "Show details"}
				</Button>
			}
			description="Workers, queues and runs behind your syncs. Only admins see this."
			title="Technical details"
		>
			{open && s ? (
				<div className="grid items-start gap-6 lg:grid-cols-2">
					<DetailTable
						empty="No workers have reported in."
						headers={["Worker", "Queues", "State"]}
						rows={s.workers.map((w) => [
							<span className="font-mono text-xs" key="id">
								{String(w.worker_id)}
							</span>,
							((w.queues as string[] | undefined) ?? []).join(", "),
							<LevelLabel
								key="s"
								label={w.online ? "Online" : "Offline"}
								level={w.online ? "ok" : "unknown"}
							/>,
						])}
					/>
					<DetailTable
						empty="No work is queued."
						headers={["Queue", "Waiting", "Oldest wait"]}
						rows={(s.queues as unknown as Queue[]).map((q) => [
							<span className="font-mono text-xs" key="n">
								{q.name}
							</span>,
							num(q.pending ?? 0),
							q.oldest_pending_seconds
								? duration(q.oldest_pending_seconds * 1000)
								: "—",
						])}
					/>
					<DetailTable
						empty="No syncs are in flight."
						headers={["Sync state", "Count"]}
						rows={[
							...Object.entries(s.runs).map(([k, v]) => [humanize(k), num(v)]),
							["Running over 15 minutes", num(s.stuck_runs)],
						]}
					/>
					<DetailTable
						empty="No open alerts."
						headers={["Alert level", "Open"]}
						rows={Object.entries(s.alert_counts)
							.filter(([, n]) => n)
							.map(([k, v]) => [humanize(k), num(v)])}
					/>
				</div>
			) : null}
		</Section>
	);
}
