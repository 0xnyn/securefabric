"use client";

import { unwrap } from "@securefabric/client";
import { cn } from "@securefabric/ui/lib/utils";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCwIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import {
	CopyField,
	KeyValue,
	PageBody,
	PageHeader,
	Tabs,
} from "@/components/common";
import {
	ConfirmButton,
	ConnectorLogo,
	errorText,
	HealthBadge,
	QueryState,
	Section,
	StatusBadge,
	When,
} from "@/components/kit";
import {
	compactValues,
	type JsonSchema,
	SchemaForm,
} from "@/components/schema-form";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import {
	Badge,
	Card,
	Field,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { num } from "@/lib/format";
import {
	type Connection,
	GRANT_TONES,
	healthInfo,
	JOB_TONES,
	STATE_TONES,
} from "@/lib/types";
import { FindingsExplorer, ResourcesExplorer } from "./explorers";

type Tab =
	| "overview"
	| "jobs"
	| "findings"
	| "resources"
	| "authorization"
	| "settings";

const idem = () => ({ "Idempotency-Key": crypto.randomUUID() });

export function useConnection(id: string) {
	const { client, env } = useEnv();
	return useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/connections/{connection_id}", {
					params: { path: { connection_id: id } },
				})
			),
		queryKey: ["connections", env.id, id],
		refetchInterval: (q) =>
			q.state.data?.state === "PENDING" ||
			q.state.data?.health.name === "INITIALIZING"
				? 3000
				: 30_000,
	});
}

export function ConnectionView({ id }: { id: string }) {
	const connection = useConnection(id);
	const [tab, setTab] = useState<Tab>("overview");
	const { client, env } = useEnv();
	const href = useHref();
	const queryClient = useQueryClient();
	const org = useQuery({
		enabled: Boolean(connection.data),
		queryFn: () =>
			unwrap(
				client.GET("/v1/organizations/{organization_id}", {
					params: {
						path: { organization_id: connection.data?.organization_id ?? "" },
					},
				})
			),
		queryKey: ["organizations", env.id, connection.data?.organization_id],
	});
	const sync = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/connections/{connection_id}/jobs", {
					body: {},
					headers: idem(),
					params: { path: { connection_id: id } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't start a sync", { description: errorText(e) }),
		onSuccess: async (job) => {
			toast.success("Sync queued", {
				description: `Job ${job.id.slice(0, 8)}`,
			});
			await queryClient.invalidateQueries({ queryKey: ["jobs", env.id, id] });
		},
	});
	const c = connection.data;
	return (
		<QueryState query={connection}>
			{c ? (
				<>
					<PageHeader
						actions={
							<Button
								disabled={sync.isPending || c.state !== "ACTIVE"}
								onClick={() => sync.mutate()}
								variant="primary"
							>
								<RefreshCwIcon /> Sync now
							</Button>
						}
						description={
							<span className="flex flex-wrap items-center gap-2">
								<Link
									className="hover:underline"
									href={href(`/organizations/${c.organization_id}`)}
								>
									{org.data?.name ?? "Organization"}
								</Link>
								<span>·</span>
								<span className="font-mono text-xs">{c.id}</span>
								{c.is_sandbox ? <Badge>sandbox</Badge> : null}
							</span>
						}
						title={
							<span className="flex items-center gap-3">
								<ConnectorLogo id={c.vendor} size={32} />
								{c.identifier ?? c.vendor}
								<StatusBadge tones={STATE_TONES} value={c.state} />
								<HealthBadge health={c.health} />
							</span>
						}
					>
						<Tabs
							className="px-4 sm:px-6"
							onChange={setTab}
							tabs={[
								{ label: "Overview", value: "overview" },
								{ label: "Jobs", value: "jobs" },
								{ label: "Findings", value: "findings" },
								{ label: "Resources", value: "resources" },
								{ label: "Authorization", value: "authorization" },
								{ label: "Settings", value: "settings" },
							]}
							value={tab}
						/>
					</PageHeader>
					<PageBody>
						{tab === "overview" ? <Overview connection={c} /> : null}
						{tab === "jobs" ? <Jobs connectionId={id} /> : null}
						{tab === "findings" ? (
							<FindingsExplorer scope={{ connectionId: id }} />
						) : null}
						{tab === "resources" ? (
							<ResourcesExplorer scope={{ connectionId: id }} />
						) : null}
						{tab === "authorization" ? <Authorization connection={c} /> : null}
						{tab === "settings" ? <Settings connection={c} /> : null}
					</PageBody>
				</>
			) : null}
		</QueryState>
	);
}

function Overview({ connection: c }: { connection: Connection }) {
	const { client, env } = useEnv();
	const info = healthInfo(c.health.name);
	const history = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/connections/{connection_id}/health/history", {
					params: { path: { connection_id: c.id } },
				})
			),
		queryKey: ["health-history", env.id, c.id],
	});
	return (
		<div className="grid gap-8">
			<Section title="Health">
				<Card className="grid gap-3 p-5">
					<div className="flex flex-wrap items-center gap-3">
						<HealthBadge health={c.health} />
						<span className="text-muted-foreground text-sm">
							{c.health.status}
							{(c.health.resolution_owner ?? info.owner)
								? ` · ${c.health.resolution_owner ?? info.owner} to resolve`
								: ""}
							{" · since "}
							<When value={c.health_changed_at} />
						</span>
					</div>
					{c.health.description ? (
						<p className="text-sm">{c.health.description}</p>
					) : null}
					{c.pending_detail ? (
						<p className="text-muted-foreground text-sm">{c.pending_detail}</p>
					) : null}
					{c.health.details?.length ? (
						<ul className="text-muted-foreground list-disc pl-5 text-sm">
							{c.health.details.map((d, i) => (
								// biome-ignore lint/suspicious/noArrayIndexKey: details have no id
								<li key={i}>
									{String(d.message ?? d.detail ?? JSON.stringify(d))}
								</li>
							))}
						</ul>
					) : null}
				</Card>
			</Section>
			<Section
				description="What each stream can read, how often it runs, and how fresh its data is"
				title="Streams"
			>
				<Card>
					<Table>
						<thead>
							<Tr>
								<Th>Stream</Th>
								<Th>Grant</Th>
								<Th>Schedule</Th>
								<Th>Last success</Th>
								<Th>Next run</Th>
								<Th className="text-right">Records</Th>
							</Tr>
						</thead>
						<tbody>
							{(c.streams ?? []).map((s) => (
								<Tr key={s.name}>
									<Td>
										<div className="font-medium">{s.name}</div>
										<div className="text-muted-foreground text-xs">
											{s.object.replaceAll("_", " ")}
											{s.enabled ? "" : " · disabled"}
										</div>
									</Td>
									<Td>
										<StatusBadge tones={GRANT_TONES} value={s.grant} />
										{s.grant_detail ? (
											<div className="text-muted-foreground mt-1 max-w-xs text-xs">
												{s.grant_detail}
											</div>
										) : null}
									</Td>
									<Td className="text-xs">
										{s.interval_s
											? `every ${Math.round(s.interval_s / 60)} min`
											: "—"}
										{s.schedule_state ? (
											<div className="text-muted-foreground">
												{s.schedule_state.toLowerCase()}
											</div>
										) : null}
									</Td>
									<Td>
										<When value={s.last_success_at} />
									</Td>
									<Td>
										<When value={s.next_run_at} />
									</Td>
									<Td className="text-right tabular-nums">
										{num(s.record_count)}
										{s.deleted_count ? (
											<div className="text-muted-foreground text-xs">
												{num(s.deleted_count)} deleted
											</div>
										) : null}
									</Td>
								</Tr>
							))}
						</tbody>
					</Table>
				</Card>
			</Section>
			<Section title="Health history">
				<QueryState
					empty={{
						description: "No transitions yet.",
						title: "No history",
						when: (history.data ?? []).length === 0,
					}}
					query={history}
					rows={2}
				>
					<Card>
						<Table>
							<tbody>
								{history.data?.map((h) => (
									<Tr key={`${h.at}-${h.to_code}`}>
										<Td className="w-40">
											<When value={h.at} />
										</Td>
										<Td>
											{h.from_code ? (
												<HealthBadge health={h.from_code} />
											) : (
												<span className="text-muted-foreground">new</span>
											)}
											{" → "}
											<HealthBadge health={h.to_code} />
										</Td>
									</Tr>
								))}
							</tbody>
						</Table>
					</Card>
				</QueryState>
			</Section>
		</div>
	);
}

function Jobs({ connectionId }: { connectionId: string }) {
	const { client, env } = useEnv();
	const href = useHref();
	const jobs = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/connections/{connection_id}/jobs", {
					params: {
						path: { connection_id: connectionId },
						query: { limit: 50 },
					},
				})
			),
		queryKey: ["jobs", env.id, connectionId],
		refetchInterval: (q) =>
			q.state.data?.some((j) => j.status === "QUEUED" || j.status === "RUNNING")
				? 3000
				: false,
	});
	return (
		<QueryState
			empty={{
				description: "Jobs appear when a sync runs.",
				title: "No jobs yet",
				when: (jobs.data ?? []).length === 0,
			}}
			query={jobs}
		>
			<Card>
				<Table>
					<thead>
						<Tr>
							<Th>Job</Th>
							<Th>Type</Th>
							<Th>Status</Th>
							<Th>Requested by</Th>
							<Th>Started</Th>
							<Th>Finished</Th>
						</Tr>
					</thead>
					<tbody>
						{jobs.data?.map((j) => (
							<Tr className="hover:bg-muted/40" key={j.id}>
								<Td>
									<Link
										className="font-mono text-xs hover:underline"
										href={href(`/jobs/${j.id}`)}
									>
										{j.id.slice(0, 8)}
									</Link>
								</Td>
								<Td className="text-xs">{j.type.toLowerCase()}</Td>
								<Td>
									<StatusBadge tones={JOB_TONES} value={j.status} />
									{j.failure_reason ? (
										<div className="text-muted-foreground mt-1 max-w-xs truncate text-xs">
											{j.failure_reason}
										</div>
									) : null}
								</Td>
								<Td className="text-xs">{j.requested_by ?? "schedule"}</Td>
								<Td>
									<When value={j.started_at} />
								</Td>
								<Td>
									<When value={j.finished_at} />
								</Td>
							</Tr>
						))}
					</tbody>
				</Table>
			</Card>
		</QueryState>
	);
}

function Authorization({ connection: c }: { connection: Connection }) {
	const { client } = useEnv();
	const [link, setLink] = useState<string | null>(null);
	const reauth = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/connect_sessions", {
					body: { connection_id: c.id, organization_id: c.organization_id },
					headers: idem(),
				})
			),
		onError: (e) =>
			toast.error("Couldn't create a link", { description: errorText(e) }),
		onSuccess: (s) => setLink(s.url),
	});
	const a = c.authorization;
	return (
		<div className="grid gap-6">
			<Card className="p-5">
				{a ? (
					<KeyValue
						items={[
							{ label: "Auth mode", value: a.auth_mode },
							{
								label: "Fields set",
								value: a.fields_set.length
									? a.fields_set.map((f) => (
											<Badge className="mr-1" key={f}>
												{f}
											</Badge>
										))
									: "—",
							},
							{ label: "Rotated", value: <When value={a.rotated_at} /> },
							{
								label: "Last token refresh",
								value: <When value={a.last_refresh_at} />,
							},
							{
								label: "Refresh exhausted",
								value: a.refresh_exhausted ? "yes" : "no",
							},
						]}
					/>
				) : (
					<p className="text-muted-foreground text-sm">
						No credentials recorded yet.
					</p>
				)}
				<p className="text-muted-foreground mt-4 text-xs">
					Credential values are write-only and never returned.
				</p>
			</Card>
			<Section
				action={
					<Button
						disabled={reauth.isPending}
						onClick={() => reauth.mutate()}
						size="sm"
						variant="outline"
					>
						Create re-authorization link
					</Button>
				}
				description="Send the customer a hosted link to replace credentials or re-install the app. The connection keeps its id and data."
				title="Re-authorize"
			>
				{link ? (
					<Field help="Valid for 30 minutes, single use" label="Link">
						<CopyField label="Re-authorization link" value={link} />
					</Field>
				) : null}
			</Section>
		</div>
	);
}

function Settings({ connection: c }: { connection: Connection }) {
	const { client, env } = useEnv();
	const href = useHref();
	const router = useRouter();
	const queryClient = useQueryClient();
	const connector = useQuery({
		queryFn: () =>
			unwrap(
				api.GET("/v1/connectors/{connector_id}", {
					params: { path: { connector_id: c.vendor } },
				})
			),
		queryKey: ["connectors", c.vendor],
	});
	const [opts, setOpts] = useState<Record<string, unknown>>(c.options);
	const refresh = () =>
		queryClient.invalidateQueries({ queryKey: ["connections", env.id] });
	const patch = useMutation({
		mutationFn: (body: {
			state?: "ACTIVE" | "PAUSED";
			options?: Record<string, unknown>;
		}) =>
			unwrap(
				client.PATCH("/v1/connections/{connection_id}", {
					body,
					params: { path: { connection_id: c.id } },
				})
			),
		onError: (e) => toast.error("Couldn't save", { description: errorText(e) }),
		onSuccess: async () => {
			toast.success("Saved");
			await refresh();
		},
	});
	const test = useMutation({
		mutationFn: () =>
			unwrap(
				client.GET("/v1/connections/{connection_id}/test", {
					params: { path: { connection_id: c.id }, query: { wait: 15 } },
				})
			),
		onError: (e) => toast.error("Test failed", { description: errorText(e) }),
		onSuccess: (r) =>
			r.is_valid
				? toast.success("Credentials work", {
						description: Object.entries(r.grants)
							.map(([k, v]) => `${k}: ${v}`)
							.join(" · "),
					})
				: toast.error("Credentials rejected", {
						description: r.message ?? undefined,
					}),
	});
	const reset = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/connections/{connection_id}/reset", {
					body: { wipe: false },
					headers: idem(),
					params: { path: { connection_id: c.id } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't reset", { description: errorText(e) }),
		onSuccess: () =>
			toast.success("Full resync queued", {
				description: "Cursors cleared; data is kept and reconciled.",
			}),
	});
	const remove = useMutation({
		mutationFn: () =>
			unwrap(
				client.DELETE("/v1/connections/{connection_id}", {
					params: { path: { connection_id: c.id } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't delete", { description: errorText(e) }),
		onSuccess: async () => {
			await refresh();
			router.push(href("/connections"));
		},
	});
	const schema = connector.data?.options_schema as JsonSchema | undefined;
	return (
		<div className="grid max-w-2xl gap-8">
			{schema?.properties && Object.keys(schema.properties).length ? (
				<Section title="Options">
					<Card className="grid gap-4 p-5">
						<SchemaForm
							idPrefix="opts"
							onChange={setOpts}
							schema={schema}
							values={opts}
						/>
						<div>
							<Button
								disabled={patch.isPending}
								onClick={() => patch.mutate({ options: compactValues(opts) })}
								size="sm"
								variant="primary"
							>
								Save options
							</Button>
						</div>
					</Card>
				</Section>
			) : null}
			<Section title="Operations">
				<Card className="divide-border grid divide-y">
					<Row
						description="Calls the vendor with the stored credentials and reports per-stream access."
						title="Test credentials"
					>
						<Button
							disabled={test.isPending}
							onClick={() => test.mutate()}
							size="sm"
							variant="outline"
						>
							Test
						</Button>
					</Row>
					<Row
						description={
							c.state === "PAUSED"
								? "Scheduled syncs are stopped."
								: "Stops scheduled syncs; data stays readable."
						}
						title={c.state === "PAUSED" ? "Resume" : "Pause"}
					>
						<Button
							disabled={
								patch.isPending ||
								!(c.state === "ACTIVE" || c.state === "PAUSED")
							}
							onClick={() =>
								patch.mutate({
									state: c.state === "PAUSED" ? "ACTIVE" : "PAUSED",
								})
							}
							size="sm"
							variant="outline"
						>
							{c.state === "PAUSED" ? "Resume" : "Pause"}
						</Button>
					</Row>
					<Row
						description="Clears every stream's cursor and runs a full sync; records missing afterwards are deleted."
						title="Reset"
					>
						<Button
							disabled={reset.isPending}
							onClick={() => reset.mutate()}
							size="sm"
							variant="outline"
						>
							Reset
						</Button>
					</Row>
					<Row
						description="Soft-deletes the connection and its data, and uninstalls where the vendor allows."
						title="Delete"
					>
						<ConfirmButton
							confirmLabel="Delete connection"
							description="Its data is soft-deleted and the vendor app is uninstalled where possible. This can't be undone from the dashboard."
							disabled={remove.isPending}
							onConfirm={() => remove.mutate()}
							title="Delete this connection?"
						>
							Delete
						</ConfirmButton>
					</Row>
				</Card>
			</Section>
		</div>
	);
}

function Row({
	title,
	description,
	children,
}: {
	title: string;
	description: string;
	children: React.ReactNode;
}) {
	return (
		<div className="flex items-center justify-between gap-4 p-4">
			<div className="grid gap-0.5">
				<span className="text-sm font-medium">{title}</span>
				<span className="text-muted-foreground text-xs">{description}</span>
			</div>
			{children}
		</div>
	);
}

// ---------------------------------------------------------------------------
// Job detail

export function JobView({ id }: { id: string }) {
	const { client, env } = useEnv();
	const href = useHref();
	const queryClient = useQueryClient();
	const job = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/jobs/{job_id}", { params: { path: { job_id: id } } })
			),
		queryKey: ["job", env.id, id],
		refetchInterval: (q) =>
			q.state.data?.status === "QUEUED" || q.state.data?.status === "RUNNING"
				? 2000
				: false,
	});
	const logs = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/jobs/{job_id}/logs", {
					params: { path: { job_id: id }, query: { limit: 500 } },
				})
			),
		queryKey: ["job-logs", env.id, id, job.data?.status],
	});
	const cancel = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/jobs/{job_id}/cancel", {
					headers: idem(),
					params: { path: { job_id: id } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't cancel", { description: errorText(e) }),
		onSuccess: () =>
			queryClient.invalidateQueries({ queryKey: ["job", env.id, id] }),
	});
	const j = job.data;
	return (
		<QueryState query={job}>
			{j ? (
				<>
					<PageHeader
						actions={
							j.status === "QUEUED" || j.status === "RUNNING" ? (
								<Button
									disabled={cancel.isPending}
									onClick={() => cancel.mutate()}
									variant="outline"
								>
									Cancel job
								</Button>
							) : null
						}
						description={
							<Link
								className="hover:underline"
								href={href(`/connections/${j.connection_id}`)}
							>
								Connection {j.connection_id.slice(0, 8)}
							</Link>
						}
						title={
							<span className="flex items-center gap-3">
								{j.type.toLowerCase()} job{" "}
								<span className="font-mono text-base">{j.id.slice(0, 8)}</span>
								<StatusBadge tones={JOB_TONES} value={j.status} />
							</span>
						}
					/>
					<PageBody className="grid gap-8">
						<Card className="p-5">
							<KeyValue
								items={[
									{
										label: "Requested by",
										value: j.requested_by ?? "schedule",
									},
									{ label: "Created", value: <When value={j.created_at} /> },
									{ label: "Started", value: <When value={j.started_at} /> },
									{ label: "Finished", value: <When value={j.finished_at} /> },
									{
										label: "Health",
										value: j.health_code ? (
											<HealthBadge health={j.health_code} />
										) : (
											"—"
										),
									},
									{ label: "Failure", value: j.failure_reason ?? "—" },
								]}
							/>
						</Card>
						<Section title="Streams">
							<Card>
								<Table>
									<thead>
										<Tr>
											<Th>Stream</Th>
											<Th>Mode</Th>
											<Th>State</Th>
											<Th className="text-right">Added</Th>
											<Th className="text-right">Updated</Th>
											<Th className="text-right">Deleted</Th>
											<Th className="text-right">Unchanged</Th>
											<Th className="text-right">Requests</Th>
										</Tr>
									</thead>
									<tbody>
										{(j.streams ?? []).map((s) => (
											<Tr key={s.id}>
												<Td>
													<div className="font-medium">{s.stream}</div>
													{s.error ? (
														<div className="text-destructive max-w-xs text-xs">
															{String(
																s.error.message ??
																	s.error.code ??
																	JSON.stringify(s.error)
															)}
														</div>
													) : null}
													{s.warning ? (
														<div className="text-muted-foreground max-w-xs text-xs">
															{s.warning}
														</div>
													) : null}
												</Td>
												<Td className="text-xs">{s.mode.toLowerCase()}</Td>
												<Td>
													<Badge>{s.state.toLowerCase()}</Badge>
												</Td>
												<Td className="text-right tabular-nums">
													{num(s.added)}
												</Td>
												<Td className="text-right tabular-nums">
													{num(s.updated)}
												</Td>
												<Td className="text-right tabular-nums">
													{num(s.deleted)}
												</Td>
												<Td className="text-right tabular-nums">
													{num(s.unchanged)}
												</Td>
												<Td className="text-right tabular-nums">
													{num(s.vendor_requests)}
												</Td>
											</Tr>
										))}
									</tbody>
								</Table>
							</Card>
						</Section>
						<Section title="Logs">
							<QueryState
								empty={{
									description: "No log lines yet.",
									title: "Empty",
									when: (logs.data ?? []).length === 0,
								}}
								query={logs}
							>
								<LogLines lines={logs.data ?? []} />
							</QueryState>
						</Section>
					</PageBody>
				</>
			) : null}
		</QueryState>
	);
}

const LEVEL_CLASS: Record<string, string> = {
	error: "text-destructive",
	warn: "text-amber-500",
	warning: "text-amber-500",
};

export function LogLines({
	lines,
}: {
	lines: {
		at: string;
		level: string;
		kind: string;
		message: string;
		http: Record<string, unknown> | null;
		stream?: string | null;
	}[];
}) {
	return (
		<div className="border-border bg-ds-shell max-h-[32rem] overflow-auto rounded-md border font-mono text-xs">
			{lines.map((l, i) => (
				<div
					className="border-border/50 flex gap-3 border-b px-3 py-1.5 last:border-0"
					// biome-ignore lint/suspicious/noArrayIndexKey: log lines are ordered and immutable
					key={i}
				>
					<span className="text-muted-foreground shrink-0">
						{l.at.slice(11, 23)}
					</span>
					<span
						className={cn(
							"shrink-0",
							LEVEL_CLASS[l.level] ?? "text-muted-foreground"
						)}
					>
						{l.level}
					</span>
					{l.stream ? (
						<span className="text-muted-foreground shrink-0">{l.stream}</span>
					) : null}
					<span className="min-w-0 break-all">
						{l.message}
						{l.http ? (
							<span className="text-muted-foreground">
								{" "}
								{String(l.http.method ?? "")}{" "}
								{String(l.http.url ?? l.http.path ?? "")}{" "}
								{String(l.http.status ?? "")}
								{l.http.duration_ms === undefined
									? ""
									: ` ${String(l.http.duration_ms)}ms`}
							</span>
						) : null}
					</span>
				</div>
			))}
		</div>
	);
}
