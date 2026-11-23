"use client";

import { formatDistanceToNowStrict } from "date-fns";
import { ActivityIcon, RefreshCwIcon } from "lucide-react";
import { PageBody, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import {
	Badge,
	Card,
	CardFooter,
	CardHeader,
	Dot,
	EmptyState,
	Mono,
	Table,
	Td,
	Th,
	type Tone,
	Tr,
} from "@/components/ui/primitives";
import {
	type StatusLevel,
	type SystemStatus,
	useSystemStatus,
} from "@/hooks/queries/status";
import { API_URL } from "@/lib/api";

/** Exhaustive over the API's levels: a new level fails the typecheck here. */
const LEVEL_TONES: Record<StatusLevel, Tone> = {
	degraded: "warn",
	down: "error",
	ok: "ok",
	unknown: "neutral",
};

const LEVEL_LABELS: Record<StatusLevel, string> = {
	degraded: "Degraded",
	down: "Down",
	ok: "Operational",
	unknown: "Unknown",
};

const COMPONENT_LABELS: Record<string, string> = {
	database: "Database",
	migrations: "Migrations",
	queue: "Task queue",
	worker: "Worker",
	workspace: "Workspace",
};

function formatBytes(bytes: number | null): string {
	if (bytes === null) {
		return "–";
	}
	const mb = bytes / 1024 / 1024;
	return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(1)} MB`;
}

function formatUptime(seconds: number | null): string {
	if (seconds === null) {
		return "–";
	}
	const h = Math.floor(seconds / 3600);
	const m = Math.floor((seconds % 3600) / 60);
	return h ? `${h}h ${m}m` : `${m}m ${Math.floor(seconds % 60)}s`;
}

export function StatusView() {
	const { data, error, isFetching, refetch } = useSystemStatus();
	return (
		<>
			<PageHeader
				actions={
					<Button onClick={() => refetch()} size="sm">
						<RefreshCwIcon
							className={isFetching ? "animate-spin" : undefined}
						/>
						Refresh
					</Button>
				}
				description={
					<>
						Live health of the stack behind this dash, from{" "}
						<Mono>GET /api/v1/status</Mono>. Run <Mono>make status</Mono> for
						the same report (plus local tooling) in your terminal.
					</>
				}
				title="Status"
			/>
			<PageBody className="grid gap-6">
				{data ? (
					<StatusReport status={data} />
				) : (
					<Card>
						<EmptyState
							description={
								error
									? `The API at ${API_URL} isn't answering (${error.message}). Start it with make dev-api.`
									: "Checking the API…"
							}
							icon={<ActivityIcon />}
							title={error ? "API unreachable" : "Loading"}
						/>
					</Card>
				)}
			</PageBody>
		</>
	);
}

function StatusReport({ status }: { status: SystemStatus }) {
	return (
		<>
			<Card>
				<CardHeader
					action={
						<Badge tone={LEVEL_TONES[status.status]}>
							<Dot tone={LEVEL_TONES[status.status]} />
							{LEVEL_LABELS[status.status]}
						</Badge>
					}
					description={`API ${status.version} · ${status.environment} · up ${formatUptime(status.uptimeSeconds)}`}
					title="Overall"
				/>
				<ul className="divide-border divide-y">
					{status.components.map((c) => (
						<li className="flex items-center gap-3 px-5 py-3" key={c.name}>
							<Dot tone={LEVEL_TONES[c.status]} />
							<span className="w-28 shrink-0 text-sm font-medium">
								{COMPONENT_LABELS[c.name] ?? c.name}
							</span>
							<span className="text-muted-foreground min-w-0 flex-1 truncate text-sm">
								{c.summary}
							</span>
							<Badge tone={LEVEL_TONES[c.status]}>
								{LEVEL_LABELS[c.status]}
							</Badge>
						</li>
					))}
				</ul>
				<CardFooter>
					<span>
						Checked{" "}
						{formatDistanceToNowStrict(status.checkedAt, { addSuffix: true })}
					</span>
					<span>Refreshes every 5s</span>
				</CardFooter>
			</Card>

			<div className="grid items-start gap-6 xl:grid-cols-2">
				<WorkersCard status={status} />
				<QueuesCard status={status} />
				<DatabaseCard status={status} />
				<EnvironmentsCard status={status} />
			</div>
		</>
	);
}

function WorkersCard({ status }: { status: SystemStatus }) {
	return (
		<Card>
			<CardHeader
				description="Each worker upserts a heartbeat every 5s; silent for 20s means offline."
				title="Workers"
			/>
			{status.workers.length ? (
				<Table>
					<thead>
						<Tr>
							<Th>Worker</Th>
							<Th>Queue</Th>
							<Th>Concurrency</Th>
							<Th>Last seen</Th>
						</Tr>
					</thead>
					<tbody>
						{status.workers.map((w) => (
							<Tr key={w.workerId}>
								<Td>
									<span className="flex items-center gap-2">
										<Dot tone={w.online ? "ok" : "error"} />
										<Mono>{w.workerId}</Mono>
									</span>
								</Td>
								<Td>{w.queue}</Td>
								<Td>{w.concurrency}</Td>
								<Td>
									{formatDistanceToNowStrict(w.lastSeenAt, { addSuffix: true })}
								</Td>
							</Tr>
						))}
					</tbody>
				</Table>
			) : (
				<EmptyState
					description="Syncs stay RUNNING until one starts. Run make dev-worker."
					icon={<ActivityIcon />}
					title="No workers have checked in"
				/>
			)}
		</Card>
	);
}

function QueuesCard({ status }: { status: SystemStatus }) {
	return (
		<Card>
			<CardHeader
				description="Absurd durable task queues and what's in them."
				title="Queues"
			/>
			{status.queues.length ? (
				<Table>
					<thead>
						<Tr>
							<Th>Queue</Th>
							<Th>Pending</Th>
							<Th>Running</Th>
							<Th>Sleeping</Th>
							<Th>Done</Th>
							<Th>Failed</Th>
						</Tr>
					</thead>
					<tbody>
						{status.queues.map((q) => (
							<Tr key={q.name}>
								<Td>
									<Mono>{q.name}</Mono>
								</Td>
								<Td>{q.pending}</Td>
								<Td>{q.running}</Td>
								<Td>{q.sleeping}</Td>
								<Td>{q.completed}</Td>
								<Td>{q.failed ? <Badge tone="error">{q.failed}</Badge> : 0}</Td>
							</Tr>
						))}
					</tbody>
				</Table>
			) : (
				<EmptyState
					description="The worker creates the default queue when it starts."
					icon={<ActivityIcon />}
					title="No queues yet"
				/>
			)}
			{status.tasks.length ? (
				<CardFooter className="flex-wrap justify-start">
					{status.tasks.map((t) => (
						<span key={`${t.taskName}:${t.state}`}>
							<Mono>{t.taskName}</Mono> {t.state} {t.count}
						</span>
					))}
				</CardFooter>
			) : null}
		</Card>
	);
}

function DatabaseCard({ status }: { status: SystemStatus }) {
	const { database: db, migrations } = status;
	const rows: [string, React.ReactNode][] = [
		["Reachable", db.reachable ? "Yes" : "No"],
		["Server", db.serverVersion ? `Postgres ${db.serverVersion}` : "–"],
		["Database", db.database ?? "–"],
		["Latency", db.latencyMs === null ? "–" : `${db.latencyMs} ms`],
		["Size", formatBytes(db.sizeBytes)],
		[
			"Migrations",
			migrations
				? `${migrations.applied.length} applied${migrations.pending.length ? `, ${migrations.pending.length} pending` : ""}`
				: "–",
		],
	];
	return (
		<Card>
			<CardHeader title="Database" />
			<dl className="divide-border divide-y">
				{rows.map(([label, value]) => (
					<div
						className="flex justify-between gap-4 px-5 py-2.5 text-sm"
						key={label}
					>
						<dt className="text-muted-foreground">{label}</dt>
						<dd>{value}</dd>
					</div>
				))}
			</dl>
			{migrations?.pending.length ? (
				<CardFooter>
					<span>
						Pending: <Mono>{migrations.pending.join(", ")}</Mono>. Run{" "}
						<Mono>make db-migrate</Mono>.
					</span>
				</CardFooter>
			) : null}
		</Card>
	);
}

function EnvironmentsCard({ status }: { status: SystemStatus }) {
	const ws = status.workspace;
	return (
		<Card>
			<CardHeader
				description={
					ws?.seeded
						? `${ws.team} · ${ws.members} members · ${ws.runningJobs} syncs running · ${ws.failedJobsLastDay} failed in 24h`
						: "Not seeded yet"
				}
				title="Workspace"
			/>
			{ws?.environments.length ? (
				<Table>
					<thead>
						<Tr>
							<Th>Environment</Th>
							<Th>Connections</Th>
							<Th>Healthy</Th>
							<Th>Attention</Th>
							<Th>Requests 24h</Th>
						</Tr>
					</thead>
					<tbody>
						{ws.environments.map((e) => (
							<Tr key={e.slug}>
								<Td>
									<span className="flex items-center gap-2">
										{e.name}
										{e.isProduction ? <Badge tone="accent">prod</Badge> : null}
									</span>
								</Td>
								<Td>{e.connections}</Td>
								<Td>{e.healthy}</Td>
								<Td>
									{e.attention ? <Badge tone="warn">{e.attention}</Badge> : 0}
								</Td>
								<Td>
									{e.operationsLastDay}
									{e.failedOperationsLastDay ? (
										<span className="text-muted-foreground">
											{" "}
											({e.failedOperationsLastDay} failed)
										</span>
									) : null}
								</Td>
							</Tr>
						))}
					</tbody>
				</Table>
			) : null}
			{ws?.stuckJobs ? (
				<CardFooter>
					<span>
						{ws.stuckJobs} syncs have been RUNNING for over 2 minutes. Is a
						worker running?
					</span>
				</CardFooter>
			) : null}
		</Card>
	);
}
