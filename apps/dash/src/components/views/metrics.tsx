"use client";

import {
	BarList,
	bucketLabel,
	DonutChart,
	type DonutSlice,
	StackedAreaChart,
	StackedBarChart,
} from "@/components/charts";
import { PageBody, PageHeader, ProviderLogo } from "@/components/common";
import { useEnv } from "@/components/shell/env-context";
import { Select } from "@/components/ui/overlay";
import {
	Card,
	CardHeader,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";
import { getProvider } from "@/lib/catalog";
import { compact, duration, num, pct } from "@/lib/format";
import {
	breakdown,
	buildSeries,
	RANGE_CONFIG,
	RANGE_LABELS,
	RANGES,
	type Range,
	totals,
} from "@/lib/metrics";
import { HEALTH } from "@/lib/types";
import { useSearchParam } from "@/lib/use-search-param";
import { StatTile } from "./shared";

/** Failures on the baseline in the warn status colour, volume above in the
 * accent, so the top line always traces the total. */
const REQUEST_SERIES = [
	{ color: "var(--ds-warn)", key: "failed", label: "4xx / 5xx" },
	{ color: "var(--ds-accent)", key: "ok", label: "2xx" },
];
const SYNC_SERIES = [
	{ color: "var(--ds-warn)", key: "failed", label: "Failed" },
	{ color: "var(--ds-accent)", key: "ok", label: "Succeeded" },
];
/** Health is state, so it wears the status palette, never series hues. */
const TONE_COLOR: Record<string, string> = {
	accent: "var(--ds-accent)",
	busy: "var(--ds-accent)",
	error: "var(--destructive)",
	neutral: "var(--muted-foreground)",
	ok: "var(--ds-success)",
	warn: "var(--ds-warn)",
};

export function MetricsView() {
	const { env } = useEnv();
	const [range, setRange] = useSearchParam<Range>("range", RANGES, "7d");
	const series = buildSeries(env, range);
	const t = totals(series, env);
	const { bucket } = RANGE_CONFIG[range];
	const apiOps = env.operations.filter((o) => o.type === "api");
	const syncOps = env.operations.filter((o) => o.type === "sync");
	const endpoints = breakdown(apiOps, (o) => o.path ?? null, t.requests);
	const byIntegration = breakdown(syncOps, (o) => o.integrationId, t.records);
	const health = new Map<string, DonutSlice>();
	for (const c of env.connections) {
		const { label, tone } = HEALTH[c.health];
		const slice = health.get(label) ?? {
			color: TONE_COLOR[tone] ?? "var(--muted-foreground)",
			key: c.health.toLowerCase(),
			label,
			value: 0,
		};
		slice.value += 1;
		health.set(label, slice);
	}
	const errorsByCode = breakdown(
		apiOps.filter((o) => (o.statusCode ?? 200) >= 400),
		(o) => String(o.statusCode),
		t.errors
	);

	return (
		<>
			<PageHeader
				actions={
					<div className="w-44">
						<Select
							ariaLabel="Time range"
							onChange={setRange}
							options={RANGES.map((r) => ({
								label: RANGE_LABELS[r],
								value: r,
							}))}
							value={range}
						/>
					</div>
				}
				description={`API traffic, sync throughput and connection health in ${env.name}.`}
				title="Metrics"
			/>
			<PageBody className="grid gap-6">
				<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
					<StatTile
						hint={RANGE_LABELS[range]}
						label="API requests"
						value={compact(t.requests)}
					/>
					<StatTile
						hint={`${num(t.errors)} errors`}
						label="Error rate"
						value={pct(t.errorRate, 2)}
					/>
					<StatTile
						hint={`p95 ${duration(t.p95)}`}
						label="p50 latency"
						value={duration(t.p50)}
					/>
					<StatTile
						hint={`${compact(t.records)} records over ${num(t.syncs)} jobs`}
						label="Sync success"
						value={pct(t.syncSuccess)}
					/>
				</div>

				<Card>
					<CardHeader description={RANGE_LABELS[range]} title="API requests" />
					<div className="px-3 py-4">
						<StackedAreaChart
							ariaLabel="API requests over time, split into successful and failed"
							data={series.map((b) => ({
								failed: b.errors,
								label: bucketLabel(b.start, bucket, range !== "24h"),
								ok: b.requests - b.errors,
							}))}
							height={240}
							series={REQUEST_SERIES}
						/>
					</div>
				</Card>

				<div className="grid gap-6 lg:grid-cols-2">
					<Card>
						<CardHeader description={RANGE_LABELS[range]} title="Sync jobs" />
						<div className="px-3 py-4">
							<StackedBarChart
								ariaLabel="Sync jobs over time, split into succeeded and failed"
								data={series.map((b) => ({
									failed: b.syncFailures,
									label: bucketLabel(b.start, bucket, range !== "24h"),
									ok: b.syncs - b.syncFailures,
								}))}
								series={SYNC_SERIES}
							/>
						</div>
					</Card>
					<Card>
						<CardHeader
							description={RANGE_LABELS[range]}
							title="Records synced by integration"
						/>
						<div className="px-4 py-4">
							<BarList
								formatValue={compact}
								items={byIntegration.map((i) => {
									const integ = env.integrations.find((x) => x.id === i.key);
									return {
										key: i.key,
										label: (
											<>
												<ProviderLogo
													provider={integ?.provider ?? i.key}
													size={18}
												/>
												{getProvider(integ?.provider ?? "")?.name ?? i.key}
											</>
										),
										value: i.value,
									};
								})}
							/>
						</div>
					</Card>
				</div>

				<div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
					<Card className="overflow-hidden">
						<CardHeader title="Top endpoints" />
						<Table>
							<thead>
								<tr>
									<Th>Endpoint</Th>
									<Th className="text-right">Requests</Th>
									<Th className="text-right">Share</Th>
								</tr>
							</thead>
							<tbody>
								{endpoints.slice(0, 8).map((e) => (
									<Tr key={e.key}>
										<Td className="text-code font-mono">
											<span className="text-muted-foreground">GET </span>
											{e.key}
										</Td>
										<Td className="text-right tabular-nums">{num(e.value)}</Td>
										<Td className="text-muted-foreground text-right tabular-nums">
											{pct(e.value / Math.max(1, t.requests), 0)}
										</Td>
									</Tr>
								))}
							</tbody>
						</Table>
					</Card>
					<div className="grid content-start gap-6">
						<Card>
							<CardHeader title="Connections by health" />
							<div className="px-4 py-4">
								<DonutChart
									ariaLabel="Connections by health"
									slices={[...health.values()]}
									total={env.connections.length}
									totalLabel="connections"
								/>
							</div>
						</Card>
						<Card>
							<CardHeader title="Errors by status code" />
							<div className="px-4 py-4">
								{errorsByCode.length ? (
									<BarList
										items={errorsByCode.map((e) => ({
											key: e.key,
											label: <span className="font-mono">{e.key}</span>,
											value: e.value,
										}))}
									/>
								) : (
									<p className="text-muted-foreground text-sm">
										No errors in this range.
									</p>
								)}
							</div>
						</Card>
					</div>
				</div>
			</PageBody>
		</>
	);
}
