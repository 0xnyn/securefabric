"use client";

import { unwrap } from "@securefabric/client";
import { Badge } from "@securefabric/ui/components/badge";
import { Button } from "@securefabric/ui/components/button";
import { Card } from "@securefabric/ui/components/card";
import { EmptyState } from "@securefabric/ui/components/empty-state";
import { Field } from "@securefabric/ui/components/form";
import { Table, Td, Th, Tr } from "@securefabric/ui/components/table";
import { num } from "@securefabric/ui/lib/format";
import { cn } from "@securefabric/ui/lib/utils";
import { EntityAvatar } from "@securefabric/ui/patterns/avatar";
import { CopyField } from "@securefabric/ui/patterns/copy";
import { KeyValue } from "@securefabric/ui/patterns/key-value";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { Section } from "@securefabric/ui/patterns/section";
import { Tabs } from "@securefabric/ui/patterns/tabs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCwIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Gated } from "@/components/domain/access";
import { HealthBadge } from "@/components/domain/badges";
import { ConfirmButton } from "@/components/domain/confirm-button";
import { ConnectorLogo } from "@/components/domain/connector-logo";
import { errorText, QueryState } from "@/components/domain/query-state";
import {
	compactValues,
	type JsonSchema,
	SchemaForm,
} from "@/components/domain/schema-form";
import { When } from "@/components/domain/when";
import { useEnv, useHref } from "@/components/shell/env-context";
import { api } from "@/lib/api";
import { authLabel, everySeconds } from "@/lib/connector-catalog";
import {
	type Connection,
	GRANT_TONES,
	healthInfo,
	JOB_TONES,
	RUN_TONES,
	STATE_TONES,
} from "@/lib/types";
import {
	EnumBadge,
	STATE_LABELS,
	sentence,
	useConnectorInfo,
} from "./connections";
import { FindingsExplorer, ResourcesExplorer } from "./explorers";

type Tab =
	| "overview"
	| "jobs"
	| "findings"
	| "resources"
	| "authorization"
	| "settings";

const idem = () => ({ "Idempotency-Key": crypto.randomUUID() });

function labelOf(labels: Record<string, string>, value: string): string {
	return labels[value] ?? sentence(value);
}

/** Why a sync job ran (schema JobType). */
const JOB_TYPE_LABELS: Record<string, string> = {
	INITIAL: "Initial sync",
	ON_DEMAND: "Manual sync",
	RETRY: "Retry",
	SCHEDULED: "Scheduled sync",
	WEBHOOK: "Webhook sync",
};

/** Job outcomes (schema JobStatus) where the enum isn't the word. */
const JOB_STATUS_LABELS: Record<string, string> = {
	PARTIAL: "Partly succeeded",
	SUCCESS: "Succeeded",
};

/** Stream run states (schema RunState) where the enum isn't the word. */
const RUN_STATE_LABELS: Record<string, string> = {
	ADMITTED: "Starting",
	PARKED: "Waiting",
	RETRY_WAIT: "Waiting to retry",
};

/** How a stream run reads the vendor (schema Mode). */
const RUN_MODE_LABELS: Record<string, string> = {
	backfill: "Backfill",
	full: "Full read",
	incremental: "Changes only",
	targeted: "Targeted",
};

/** What a stream produces (schema ObjectType). */
const OBJECT_LABELS: Record<string, string> = {
	resource: "Resources",
	vulnerability_finding: "Findings",
};

/** A stream's schedule (sync.schedule state). */
const SCHEDULE_LABELS: Record<string, string> = {
	PAUSED: "Paused",
	STARTED: "Scheduled",
};

/** Whether a stream may read what it needs (schema GrantStatus). */
const GRANT_LABELS: Record<string, string> = {
	GRANTED: "Granted",
	NOT_ENABLED: "Not enabled",
	UNAUTHORIZED: "No access",
	UNKNOWN: "Unknown",
	UNSUPPORTED: "Unsupported",
};

/** Who has to act on a health problem (schema ResolutionOwner). */
const OWNER_LABELS: Record<string, string> = {
	CUSTOMER: "Waiting on your customer",
	Customer: "Waiting on your customer",
	PLATFORM: "Waiting on SecureFabric",
	SecureFabric: "Waiting on SecureFabric",
	VENDOR: "Waiting on the vendor",
	Vendor: "Waiting on the vendor",
};

/** Overall health (schema HealthStatus). */
const HEALTH_STATUS_LABELS: Record<string, string> = {
	HEALTHY: "Healthy",
	INITIALIZING: "Initializing",
	UNHEALTHY: "Unhealthy",
};

/** Who started a job, from `requested_by` ("schedule", "api_key:…", "verify:create"). */
function requester(value: string | null): string {
	if (!value) {
		return "Schedule";
	}
	const [kind] = value.split(":");
	switch (kind) {
		case "api_key":
			return "API key";
		case "user":
			return "Team member";
		case "support":
			return "SecureFabric support";
		case "verify":
			return "Connection check";
		case "schedule":
			return "Schedule";
		case "webhook":
			return "Vendor webhook";
		case "resume":
			return "Resumed connection";
		case "system":
			return "SecureFabric";
		default:
			return value;
	}
}

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

/** Starts an on-demand sync (POST /jobs needs jobs:execute). */
function SyncNowButton({
	connectionId,
	active,
}: {
	connectionId: string;
	active: boolean;
}) {
	const { client, env } = useEnv();
	const queryClient = useQueryClient();
	const sync = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/connections/{connection_id}/jobs", {
					body: {},
					headers: idem(),
					params: { path: { connection_id: connectionId } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't start the sync", { description: errorText(e) }),
		onSuccess: async () => {
			toast.success("Sync queued", {
				description: "It starts in a moment. Follow it on the Jobs tab.",
			});
			await queryClient.invalidateQueries({
				queryKey: ["jobs", env.id, connectionId],
			});
		},
	});
	return (
		<Gated requires={{ scope: "jobs:execute" }}>
			<Button
				disabled={sync.isPending || !active}
				onClick={() => sync.mutate()}
				variant="primary"
			>
				<RefreshCwIcon /> {sync.isPending ? "Starting…" : "Sync now"}
			</Button>
		</Gated>
	);
}

export function ConnectionView({ id }: { id: string }) {
	const connection = useConnection(id);
	const [tab, setTab] = useState<Tab>("overview");
	const { client, env } = useEnv();
	const href = useHref();
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
	const connector = useConnectorInfo();
	const c = connection.data;
	const info = connector(c?.vendor ?? "");
	return (
		<QueryState query={connection}>
			{c ? (
				<>
					<PageHeader
						actions={
							<SyncNowButton active={c.state === "ACTIVE"} connectionId={id} />
						}
						description={
							<span className="flex flex-wrap items-center gap-2">
								<Link
									className="text-foreground inline-flex items-center gap-1.5 hover:underline"
									href={href(`/organizations/${c.organization_id}`)}
								>
									<EntityAvatar
										name={org.data?.name ?? "Organization"}
										size={16}
									/>
									{org.data?.name ?? "Organization"}
								</Link>
								<span>·</span>
								<span>{info.name}</span>
								<span>·</span>
								<span className="font-mono text-xs">{c.id}</span>
								{c.is_sandbox ? <Badge>Sandbox</Badge> : null}
							</span>
						}
						title={
							<span className="flex items-center gap-3">
								<ConnectorLogo
									id={c.vendor}
									logo={info.logo}
									name={info.name}
									size={32}
								/>
								{c.identifier ?? info.name}
								<EnumBadge
									labels={STATE_LABELS}
									tones={STATE_TONES}
									value={c.state}
								/>
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
	const owner = c.health.resolution_owner ?? healthInfo(c.health.name).owner;
	const streams = c.streams ?? [];
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
							{labelOf(HEALTH_STATUS_LABELS, c.health.status)}
							{owner ? ` · ${labelOf(OWNER_LABELS, owner)}` : ""}
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
				description="What each stream can read, how often it runs and how fresh its data is."
				title="Streams"
			>
				{streams.length === 0 ? (
					<EmptyState
						description="Streams appear once the connection is verified."
						title="No streams yet"
					/>
				) : (
					<Card>
						<Table>
							<thead>
								<Tr>
									<Th>Stream</Th>
									<Th>Access</Th>
									<Th>Schedule</Th>
									<Th>Last success</Th>
									<Th>Next run</Th>
									<Th className="text-right">Records</Th>
								</Tr>
							</thead>
							<tbody>
								{streams.map((s) => (
									<Tr key={s.name}>
										<Td>
											<div className="font-mono text-sm">{s.name}</div>
											<div className="text-muted-foreground text-xs">
												{labelOf(OBJECT_LABELS, s.object)}
												{s.enabled ? "" : " · Off"}
											</div>
										</Td>
										<Td>
											<EnumBadge
												labels={GRANT_LABELS}
												tones={GRANT_TONES}
												value={s.grant}
											/>
											{s.grant_detail ? (
												<div className="text-muted-foreground mt-1 max-w-xs text-xs">
													{s.grant_detail}
												</div>
											) : null}
										</Td>
										<Td>
											{s.interval_s
												? sentence(everySeconds(s.interval_s))
												: "—"}
											{s.schedule_state ? (
												<div className="text-muted-foreground text-xs">
													{labelOf(SCHEDULE_LABELS, s.schedule_state)}
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
				)}
			</Section>
			<Section title="Health history">
				<QueryState
					empty={{
						description: "Changes to this connection's health appear here.",
						title: "No health changes yet",
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
												<span className="text-muted-foreground">Created</span>
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
				description:
					"Scheduled and manual syncs of this connection appear here.",
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
								<Td>{labelOf(JOB_TYPE_LABELS, j.type)}</Td>
								<Td>
									<EnumBadge
										labels={JOB_STATUS_LABELS}
										tones={JOB_TONES}
										value={j.status}
									/>
									{j.failure_reason ? (
										<div className="text-muted-foreground mt-1 max-w-xs truncate text-xs">
											{j.failure_reason}
										</div>
									) : null}
								</Td>
								<Td>
									<span title={j.requested_by ?? undefined}>
										{requester(j.requested_by)}
									</span>
								</Td>
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
			toast.error("Couldn't create the re-authorization link", {
				description: errorText(e),
			}),
		onSuccess: (s) => setLink(s.url),
	});
	const a = c.authorization;
	return (
		<div className="grid gap-6">
			<Card className="p-5">
				{a ? (
					<KeyValue
						items={[
							{ label: "Sign-in method", value: authLabel(a.auth_mode) },
							{
								label: "Saved credentials",
								value: a.fields_set.length
									? a.fields_set.map((f) => (
											<Badge className="mr-1 font-mono" key={f}>
												{f}
											</Badge>
										))
									: "—",
							},
							{ label: "Last rotated", value: <When value={a.rotated_at} /> },
							{
								label: "Last token refresh",
								value: <When value={a.last_refresh_at} />,
							},
							{
								label: "Token refresh",
								value: a.refresh_exhausted
									? "Failing. Re-authorize to fix it."
									: "Working",
							},
						]}
					/>
				) : (
					<p className="text-muted-foreground text-sm">
						No credentials saved yet.
					</p>
				)}
				<p className="text-muted-foreground mt-4 text-xs">
					Credential values are never shown after they're saved.
				</p>
			</Card>
			<Section
				action={
					<Gated requires={{ scope: "provisioning:write" }}>
						<Button
							disabled={reauth.isPending}
							onClick={() => reauth.mutate()}
							size="sm"
							variant="outline"
						>
							{reauth.isPending ? "Creating…" : "Create re-authorization link"}
						</Button>
					</Gated>
				}
				description="Send your customer a link to replace credentials or reinstall the app. The connection keeps its data."
				title="Re-authorize"
			>
				{link ? (
					<Field
						help="Send this to your customer. It works once, for 30 minutes."
						label="Re-authorization link"
					>
						<CopyField label="Re-authorization link" value={link} />
					</Field>
				) : null}
			</Section>
		</div>
	);
}

/** Toast and button copy for each kind of connection update. */
const PATCH_COPY = {
	ACTIVE: {
		action: "Resume syncing",
		done: "Connection resumed",
		failed: "Couldn't resume the connection",
		pending: "Resuming…",
	},
	options: {
		action: "Save options",
		done: "Options saved",
		failed: "Couldn't save the options",
		pending: "Saving…",
	},
	PAUSED: {
		action: "Pause syncing",
		done: "Connection paused",
		failed: "Couldn't pause the connection",
		pending: "Pausing…",
	},
} as const;

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
		onError: (e, body) =>
			toast.error(PATCH_COPY[body.state ?? "options"].failed, {
				description: errorText(e),
			}),
		onSuccess: async (_, body) => {
			toast.success(PATCH_COPY[body.state ?? "options"].done);
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
		onError: (e) =>
			toast.error("Couldn't test the credentials", {
				description: errorText(e),
			}),
		onSuccess: (r) =>
			r.is_valid
				? toast.success("Credentials work", {
						description: Object.entries(r.grants)
							.map(([k, v]) => `${k}: ${labelOf(GRANT_LABELS, String(v))}`)
							.join(" · "),
					})
				: toast.error("The vendor rejected the credentials", {
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
			toast.error("Couldn't start the full resync", {
				description: errorText(e),
			}),
		onSuccess: () =>
			toast.success("Full resync queued", {
				description:
					"Your data stays in place while it runs. Records the vendor no longer returns are removed at the end.",
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
			toast.error("Couldn't delete the connection", {
				description: errorText(e),
			}),
		onSuccess: async () => {
			toast.success("Connection deleted");
			await refresh();
			router.push(href("/connections"));
		},
	});
	const schema = connector.data?.options_schema as JsonSchema | undefined;
	const paused = c.state === "PAUSED";
	const name = c.identifier ?? connector.data?.name ?? c.vendor;
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
							<Gated requires={{ scope: "provisioning:write" }}>
								<Button
									disabled={patch.isPending}
									onClick={() => patch.mutate({ options: compactValues(opts) })}
									size="sm"
									variant="primary"
								>
									{patch.isPending && !patch.variables?.state
										? "Saving…"
										: "Save options"}
								</Button>
							</Gated>
						</div>
					</Card>
				</Section>
			) : null}
			<Section title="Operations">
				<Card className="divide-border grid divide-y">
					<Row
						description="Checks the saved credentials and what each stream can read."
						title="Test credentials"
					>
						<Button
							disabled={test.isPending}
							onClick={() => test.mutate()}
							size="sm"
							variant="outline"
						>
							{test.isPending ? "Testing…" : "Run test"}
						</Button>
					</Row>
					<Row
						description={
							paused
								? "Scheduled syncs are stopped. Resume to start them again."
								: "Stops scheduled syncs. Synced data stays readable."
						}
						title={paused ? "Resume syncing" : "Pause syncing"}
					>
						<Gated requires={{ scope: "provisioning:write" }}>
							<Button
								disabled={
									patch.isPending ||
									!(c.state === "ACTIVE" || c.state === "PAUSED")
								}
								onClick={() =>
									patch.mutate({ state: paused ? "ACTIVE" : "PAUSED" })
								}
								size="sm"
								variant="outline"
							>
								{patch.isPending && patch.variables?.state
									? PATCH_COPY[paused ? "ACTIVE" : "PAUSED"].pending
									: PATCH_COPY[paused ? "ACTIVE" : "PAUSED"].action}
							</Button>
						</Gated>
					</Row>
					<Row
						description="Reads everything from the vendor again. Records it no longer returns are deleted."
						title="Full resync"
					>
						<Gated requires={{ scope: "jobs:execute" }}>
							<Button
								disabled={reset.isPending}
								onClick={() => reset.mutate()}
								size="sm"
								variant="outline"
							>
								{reset.isPending ? "Starting…" : "Start full resync"}
							</Button>
						</Gated>
					</Row>
					<Row
						description="Deletes the connection and its data, and uninstalls the vendor app where possible."
						title="Delete connection"
					>
						<Gated requires={{ scope: "provisioning:write" }}>
							<ConfirmButton
								confirmLabel="Delete connection"
								description="Its synced data is deleted and the vendor app is uninstalled where possible. You can't undo this from the dashboard."
								disabled={remove.isPending}
								onConfirm={() => remove.mutate()}
								title={`Delete “${name}”?`}
							>
								{remove.isPending ? "Deleting…" : "Delete connection"}
							</ConfirmButton>
						</Gated>
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
			toast.error("Couldn't cancel the job", { description: errorText(e) }),
		onSuccess: async () => {
			toast.success("Cancellation requested");
			await queryClient.invalidateQueries({ queryKey: ["job", env.id, id] });
		},
	});
	const j = job.data;
	return (
		<QueryState query={job}>
			{j ? (
				<>
					<PageHeader
						actions={
							j.status === "QUEUED" || j.status === "RUNNING" ? (
								<Gated requires={{ scope: "jobs:execute" }}>
									<Button
										disabled={cancel.isPending}
										onClick={() => cancel.mutate()}
										variant="outline"
									>
										{cancel.isPending ? "Cancelling…" : "Cancel job"}
									</Button>
								</Gated>
							) : null
						}
						description={
							<Link
								className="hover:underline"
								href={href(`/connections/${j.connection_id}`)}
							>
								Connection{" "}
								<span className="font-mono">{j.connection_id.slice(0, 8)}</span>
							</Link>
						}
						title={
							<span className="flex items-center gap-3">
								{labelOf(JOB_TYPE_LABELS, j.type)}{" "}
								<span className="font-mono text-base">{j.id.slice(0, 8)}</span>
								<EnumBadge
									labels={JOB_STATUS_LABELS}
									tones={JOB_TONES}
									value={j.status}
								/>
							</span>
						}
					/>
					<PageBody className="grid gap-8">
						<Card className="p-5">
							<KeyValue
								items={[
									{
										label: "Requested by",
										value: (
											<span title={j.requested_by ?? undefined}>
												{requester(j.requested_by)}
											</span>
										),
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
									{ label: "Failure reason", value: j.failure_reason ?? "—" },
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
													<div className="font-mono text-sm">{s.stream}</div>
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
												<Td>{labelOf(RUN_MODE_LABELS, s.mode)}</Td>
												<Td>
													<EnumBadge
														labels={RUN_STATE_LABELS}
														tones={RUN_TONES}
														value={s.state}
													/>
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
									description: "Log lines appear here while the job runs.",
									title: "No logs yet",
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
