"use client";

import { unwrap } from "@securefabric/client";
import { useQuery } from "@tanstack/react-query";
import { PageBody, PageHeader } from "@/components/common";
import { JsonBlock, QueryState, Section, When } from "@/components/kit";
import { useEnv } from "@/components/shell/env-context";
import { Badge, Card, Table, Td, Th, Tr } from "@/components/ui/primitives";
import { num } from "@/lib/format";
import { Stat } from "./overview";

const STATUS_TONE = { degraded: "warn", down: "error", ok: "ok" } as const;
const ALERT_LEVELS = ["page", "ticket", "info"] as const;

/**
 * GET /v1/status, sent with this dashboard's credentials: an API key or a
 * session sees workers, queues, runs and alert counts; operators also see the
 * alerts themselves.
 */
export function StatusView() {
	const { client, me } = useEnv();
	const status = useQuery({
		queryFn: () => unwrap(client.GET("/v1/status")),
		queryKey: ["status", me.actor_id],
		refetchInterval: 10_000,
	});
	const s = status.data;
	return (
		<>
			<PageHeader
				actions={
					s ? (
						<Badge
							tone={
								STATUS_TONE[s.status as keyof typeof STATUS_TONE] ?? "neutral"
							}
						>
							{s.status}
						</Badge>
					) : null
				}
				description={
					s ? (
						<>
							Version {s.version} · checked <When value={s.checked_at} />
						</>
					) : (
						"API, database, workers and queues"
					)
				}
				title="Status"
			/>
			<PageBody className="grid gap-8">
				<QueryState query={status}>
					{s ? (
						<>
							{s.status !== "ok" && s.problems.length ? (
								<Card className="border-destructive/40 grid gap-1 p-4">
									<span className="text-sm font-semibold">Problems</span>
									<ul className="list-disc pl-5 text-sm">
										{s.problems.map((p) => (
											<li key={p}>{p}</li>
										))}
									</ul>
								</Card>
							) : null}
							<div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
								<Stat label="Stuck runs" value={num(s.stuck_runs)} />
								<Stat
									label="Failed runs (24h)"
									value={num(s.failed_runs_last_day)}
								/>
								{ALERT_LEVELS.map((level) => (
									<Stat
										key={level}
										label={`Open alerts: ${level}`}
										value={num(s.alert_counts[level] ?? 0)}
									/>
								))}
							</div>
							{Object.keys(s.runs).length ? (
								<Section title="Stream runs by state">
									<Card className="overflow-x-auto">
										<Table>
											<tbody>
												{Object.entries(s.runs).map(([state, n]) => (
													<Tr key={state}>
														<Td className="text-xs">
															{state.toLowerCase().replaceAll("_", " ")}
														</Td>
														<Td className="text-right tabular-nums">
															{num(n)}
														</Td>
													</Tr>
												))}
											</tbody>
										</Table>
									</Card>
								</Section>
							) : null}
							<div className="grid gap-6 lg:grid-cols-2">
								<Section title="Database">
									<JsonBlock value={s.database} />
								</Section>
								<Section title="Migrations">
									<JsonBlock value={s.migrations} />
								</Section>
							</div>
							<Section title="Workers">
								<Rows rows={s.workers} />
							</Section>
							<Section title="Queues">
								<Rows rows={s.queues} />
							</Section>
							{s.alerts.length ? (
								<Section description="Visible to operators" title="Alerts">
									<Rows rows={s.alerts} />
								</Section>
							) : null}
						</>
					) : null}
				</QueryState>
			</PageBody>
		</>
	);
}

function Rows({ rows }: { rows: Record<string, unknown>[] }) {
	if (rows.length === 0) {
		return <p className="text-muted-foreground text-sm">None.</p>;
	}
	const cols = Object.keys(rows[0] ?? {});
	return (
		<Card className="overflow-x-auto">
			<Table>
				<thead>
					<Tr>
						{cols.map((c) => (
							<Th key={c}>{c.replaceAll("_", " ")}</Th>
						))}
					</Tr>
				</thead>
				<tbody>
					{rows.map((r, i) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: status rows have no stable id
						<Tr key={i}>
							{cols.map((c) => (
								<Td className="text-xs" key={c}>
									{typeof r[c] === "object" && r[c] !== null
										? JSON.stringify(r[c])
										: String(r[c] ?? "—")}
								</Td>
							))}
						</Tr>
					))}
				</tbody>
			</Table>
		</Card>
	);
}
