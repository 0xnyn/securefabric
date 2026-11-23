"use client";

import { Card } from "@securefabric/ui/components/card";
import { EmptyState } from "@securefabric/ui/components/empty-state";
import { Select } from "@securefabric/ui/components/select";
import { Table, Td, Th, Tr } from "@securefabric/ui/components/table";
import { compact, dateShort, num } from "@securefabric/ui/lib/format";
import { StackedBarChart } from "@securefabric/ui/patterns/charts";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { Section } from "@securefabric/ui/patterns/section";
import { Stat } from "@securefabric/ui/patterns/stat";
import { useState } from "react";
import { QueryState } from "@/components/domain/query-state";
import { useUsage } from "./overview";

interface Day {
	active_connections?: number;
	api_calls?: number;
	day: string;
	jobs?: number;
	records_stored?: number;
	records_written?: number;
}

/** Usage counters (BILL-03): a live snapshot, the daily rollup, and API calls by hour. */
export function MetricsView() {
	const [days, setDays] = useState("30");
	const usage = useUsage(Number(days));
	const daily = (usage.data?.daily ?? []) as unknown as Day[];
	const live = (usage.data?.live ?? {}) as Partial<Record<string, number>>;
	const series = (
		key: keyof Day,
		label: string,
		color = "var(--ds-accent)"
	) => (
		<Section title={label}>
			<Card className="p-5">
				<StackedBarChart
					ariaLabel={label}
					data={daily.map((d) => ({
						label: dateShort(new Date(d.day).getTime()),
						[key]: Number(d[key] ?? 0),
					}))}
					series={[{ color, key, label }]}
				/>
			</Card>
		</Section>
	);
	return (
		<>
			<PageHeader
				actions={
					<Select
						ariaLabel="Time range"
						className="w-36"
						onChange={setDays}
						options={[
							{ label: "Last 7 days", value: "7" },
							{ label: "Last 30 days", value: "30" },
							{ label: "Last 90 days", value: "90" },
						]}
						value={days}
					/>
				}
				description="API calls, records and jobs in this environment over time."
				title="Metrics"
			/>
			<PageBody className="grid gap-8">
				<QueryState query={usage}>
					<div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
						<Stat
							label="Active connections"
							value={num(live.active_connections ?? 0)}
						/>
						<Stat
							label="Records stored"
							value={compact(live.records_stored ?? 0)}
						/>
						<Stat
							hint={
								live.failed_jobs_24h
									? `${num(live.failed_jobs_24h)} failed`
									: "None failed"
							}
							label="Jobs, last 24 hours"
							value={num(live.jobs_24h ?? 0)}
						/>
						<Stat
							label="API calls, last 24 hours"
							value={compact(live.api_calls_24h ?? 0)}
						/>
					</div>
					{daily.length === 0 ? (
						<EmptyState
							description="Figures update once a day, so the first ones appear tomorrow."
							title="No daily figures yet"
						/>
					) : (
						<>
							<div className="grid gap-6 lg:grid-cols-2">
								{series("api_calls", "API calls per day")}
								{series("records_written", "Records written per day")}
								{series("jobs", "Jobs per day")}
								{series("active_connections", "Billable connections")}
							</div>
							<Section title="Daily figures">
								<Card>
									<Table>
										<thead>
											<Tr>
												<Th>Day</Th>
												<Th className="text-right">Billable connections</Th>
												<Th className="text-right">Records stored</Th>
												<Th className="text-right">Records written</Th>
												<Th className="text-right">Jobs</Th>
												<Th className="text-right">API calls</Th>
											</Tr>
										</thead>
										<tbody>
											{[...daily].reverse().map((d) => (
												<Tr key={d.day}>
													<Td>{d.day}</Td>
													<Td className="text-right tabular-nums">
														{num(d.active_connections ?? 0)}
													</Td>
													<Td className="text-right tabular-nums">
														{num(d.records_stored ?? 0)}
													</Td>
													<Td className="text-right tabular-nums">
														{num(d.records_written ?? 0)}
													</Td>
													<Td className="text-right tabular-nums">
														{num(d.jobs ?? 0)}
													</Td>
													<Td className="text-right tabular-nums">
														{num(d.api_calls ?? 0)}
													</Td>
												</Tr>
											))}
										</tbody>
									</Table>
								</Card>
							</Section>
						</>
					)}
				</QueryState>
			</PageBody>
		</>
	);
}
