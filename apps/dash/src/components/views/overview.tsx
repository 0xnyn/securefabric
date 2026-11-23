"use client";

import {
	ArrowRightIcon,
	BoxesIcon,
	FlaskConicalIcon,
	PlusIcon,
	TriangleAlertIcon,
} from "lucide-react";
import Link from "next/link";
import { bucketLabel, StackedAreaChart } from "@/components/charts";
import { PageBody, PageHeader, ProviderLogo } from "@/components/common";
import { useEnv, useHref } from "@/components/shell/env-context";
import { buttonVariants } from "@/components/ui/button";
import {
	Badge,
	Card,
	CardFooter,
	CardHeader,
	Dot,
	EmptyState,
} from "@/components/ui/primitives";
import { getProvider } from "@/lib/catalog";
import { compact, mask, num, pct, plural, timeAgo } from "@/lib/format";
import { buildSeries, totals } from "@/lib/metrics";
import { HEALTH } from "@/lib/types";
import { ActivityRow, ConnectionLabel, StatTile } from "./shared";

const HOUR_MS = 3_600_000;
const TRAFFIC_SERIES = [
	{ color: "var(--ds-warn)", key: "failed", label: "4xx / 5xx" },
	{ color: "var(--ds-accent)", key: "ok", label: "2xx" },
];

export function OverviewView() {
	const { env } = useEnv();
	const href = useHref();
	const series = buildSeries(env, "24h");
	const t = totals(series, env);
	const healthy = env.connections.filter((c) => c.health === "HEALTHY");
	const attention = env.connections.filter(
		(c) => HEALTH[c.health].tone === "error" || HEALTH[c.health].tone === "warn"
	);
	const sandboxCount = env.connections.filter((c) => c.sandbox).length;
	const recent = env.operations.slice(0, 8);

	return (
		<>
			<PageHeader
				actions={
					<>
						<Link className={buttonVariants()} href={href("/catalog")}>
							<BoxesIcon />
							Browse catalog
						</Link>
						<Link
							className={buttonVariants({ variant: "primary" })}
							href={href("/connections?new=1")}
						>
							<PlusIcon />
							Add connection
						</Link>
					</>
				}
				description={
					<>
						{env.isProduction ? "Live" : "Test"} environment ·{" "}
						{plural(env.integrations.length, "integration")} ·{" "}
						{plural(env.connections.length, "connection")}
						{sandboxCount ? ` (${sandboxCount} sandbox)` : ""}
					</>
				}
				title={env.name}
			/>
			<PageBody className="grid gap-6">
				{env.integrations.length === 0 ? (
					<EmptyState
						action={
							<Link
								className={buttonVariants({ variant: "primary" })}
								href={href("/catalog")}
							>
								Browse the catalog
								<ArrowRightIcon />
							</Link>
						}
						description="Enable an integration from the catalog, then connect a sandbox account to read data in under a minute. No vendor credentials needed."
						icon={<FlaskConicalIcon className="size-4" />}
						title="This environment is empty"
					/>
				) : null}

				<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
					<StatTile
						hint="Last 24 hours, all endpoints"
						label="API requests"
						spark={series.map((b) => b.requests)}
						value={compact(t.requests)}
					/>
					<StatTile
						hint={`${num(t.syncs)} sync jobs, ${pct(t.syncSuccess)} succeeded`}
						label="Records synced"
						spark={series.map((b) => b.records)}
						value={compact(t.records)}
					/>
					<StatTile
						hint={`${attention.length} need attention`}
						label="Healthy connections"
						value={`${healthy.length} / ${env.connections.length}`}
					/>
					<StatTile
						hint={`${num(t.errors)} failed ${t.errors === 1 ? "request" : "requests"}`}
						label="Error rate"
						spark={series.map((b) => b.errors)}
						tone="error"
						value={pct(t.errorRate, 2)}
					/>
				</div>

				<div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
					<div className="grid content-start gap-6">
						<Card>
							<CardHeader
								action={
									<Link
										className="text-muted-foreground hover:text-foreground text-sm"
										href={href("/metrics?range=24h")}
									>
										Metrics
									</Link>
								}
								description="Last 24 hours"
								title="API traffic"
							/>
							<div className="px-3 py-4">
								<StackedAreaChart
									ariaLabel="API requests per hour over the last 24 hours, split into successful and failed"
									data={series.map((b) => ({
										failed: b.errors,
										label: bucketLabel(b.start, HOUR_MS),
										ok: b.requests - b.errors,
									}))}
									series={TRAFFIC_SERIES}
								/>
							</div>
						</Card>
						{attention.length > 0 ? (
							<Card>
								<CardHeader
									description="Connections whose last sync failed or is degraded."
									title={
										<span className="flex items-center gap-2">
											<TriangleAlertIcon className="text-ds-severity-high size-4" />
											Needs attention
										</span>
									}
								/>
								<ul>
									{attention.map((c) => (
										<li
											className="border-border border-b last:border-b-0"
											key={c.id}
										>
											<Link
												className="hover:bg-ds-shell flex items-center justify-between gap-4 px-5 py-3"
												href={href(`/connections/${c.id}`)}
											>
												<ConnectionLabel conn={c} />
												<div className="flex shrink-0 items-center gap-3">
													<span className="text-muted-foreground hidden text-xs md:inline">
														Owner: {HEALTH[c.health].owner}
													</span>
													<Badge
														tone={
															HEALTH[c.health].tone === "error"
																? "error"
																: "warn"
														}
													>
														{HEALTH[c.health].label}
													</Badge>
												</div>
											</Link>
										</li>
									))}
								</ul>
							</Card>
						) : null}

						<Card>
							<CardHeader
								action={
									<Link
										className="text-muted-foreground hover:text-foreground text-sm"
										href={href("/logs")}
									>
										View all logs
									</Link>
								}
								title="Recent activity"
							/>
							{recent.length === 0 ? (
								<p className="text-muted-foreground px-5 py-10 text-center text-sm">
									Nothing yet. Activity appears here as connections sync and
									your app calls the API.
								</p>
							) : (
								<div className="divide-border divide-y">
									{recent.map((op) => (
										<ActivityRow key={op.id} op={op} />
									))}
								</div>
							)}
						</Card>
					</div>

					<div className="grid content-start gap-6">
						<Card>
							<CardHeader
								action={
									<Link
										className="text-muted-foreground hover:text-foreground text-sm"
										href={href("/integrations")}
									>
										Manage
									</Link>
								}
								title="Integrations"
							/>
							<ul>
								{env.integrations.map((i) => {
									const conns = env.connections.filter(
										(c) => c.integrationId === i.id
									);
									const bad = conns.filter(
										(c) => HEALTH[c.health].tone === "error"
									).length;
									return (
										<li
											className="border-border border-b last:border-b-0"
											key={i.id}
										>
											<Link
												className="hover:bg-ds-shell flex items-center gap-3 px-5 py-3 text-sm"
												href={href(`/integrations/${i.id}`)}
											>
												<ProviderLogo provider={i.provider} size={24} />
												<span className="min-w-0 flex-1 truncate">
													{getProvider(i.provider)?.name}
												</span>
												{bad > 0 ? <Dot tone="error" /> : null}
												<span className="text-muted-foreground text-xs tabular-nums">
													{conns.length}
												</span>
											</Link>
										</li>
									);
								})}
								{env.integrations.length === 0 ? (
									<li className="text-muted-foreground px-5 py-6 text-sm">
										None enabled yet.
									</li>
								) : null}
							</ul>
						</Card>

						<Card>
							<CardHeader title="Environment" />
							<dl className="grid gap-4 px-5 py-4 text-sm">
								<div className="grid gap-1">
									<dt className="text-muted-foreground text-xs">API keys</dt>
									<dd>
										{plural(env.apiKeys.length, "key")} ·{" "}
										<span className="text-code text-muted-foreground font-mono">
											{mask(env.keys.secret)}
										</span>
									</dd>
								</div>
								<div className="grid gap-1">
									<dt className="text-muted-foreground text-xs">Webhooks</dt>
									<dd>
										{env.webhooks.length
											? plural(env.webhooks.length, "endpoint")
											: "Not configured"}
									</dd>
								</div>
								<div className="grid gap-1">
									<dt className="text-muted-foreground text-xs">Created</dt>
									<dd>{timeAgo(env.createdAt)}</dd>
								</div>
							</dl>
							<CardFooter>
								<span>Keys, webhooks and Connect branding</span>
								<Link
									className="text-foreground hover:underline"
									href={href("/settings")}
								>
									Settings
								</Link>
							</CardFooter>
						</Card>
					</div>
				</div>
			</PageBody>
		</>
	);
}
