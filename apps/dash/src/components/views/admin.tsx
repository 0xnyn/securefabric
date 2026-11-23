"use client";

import { isApiError, unwrap } from "@securefabric/client";
import { pathsV1AdminEnvironmentsEnvironment_idConnectionsConnection_idActionPostParametersPathActionValues as REPAIR_ACTIONS } from "@securefabric/client/v1";
import { Badge, type Tone } from "@securefabric/ui/components/badge";
import { Button } from "@securefabric/ui/components/button";
import { Card } from "@securefabric/ui/components/card";
import { Dialog, DialogContent } from "@securefabric/ui/components/dialog";
import { EmptyState } from "@securefabric/ui/components/empty-state";
import { Field, Input, Textarea } from "@securefabric/ui/components/form";
import { Mono } from "@securefabric/ui/components/mono";
import { Switch } from "@securefabric/ui/components/switch";
import { Table, Td, Th, Tr } from "@securefabric/ui/components/table";
import { num } from "@securefabric/ui/lib/format";
import { cn } from "@securefabric/ui/lib/utils";
import { CopyButton } from "@securefabric/ui/patterns/copy";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { Section } from "@securefabric/ui/patterns/section";
import { Tabs } from "@securefabric/ui/patterns/tabs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	CheckIcon,
	FileSearchIcon,
	RefreshCwIcon,
	SearchIcon,
	ShieldEllipsisIcon,
	WrenchIcon,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { createContext, useContext, useId, useState } from "react";
import { toast } from "sonner";
import {
	enumLabel,
	HealthBadge,
	StatusBadge,
} from "@/components/domain/badges";
import { ConfirmButton } from "@/components/domain/confirm-button";
import { JsonBlock } from "@/components/domain/json-block";
import { errorText, QueryState } from "@/components/domain/query-state";
import { When } from "@/components/domain/when";
import { useEnv, useHref } from "@/components/shell/env-context";
import {
	type Alert,
	type RepairAction,
	type RepairTask,
	RUN_TONES,
	STATE_TONES,
} from "@/lib/types";
import { useSearchParam } from "@/lib/use-search-param";

// ---------------------------------------------------------------------------
// Row shapes
//
// Alerts and repair tasks are typed by the API (`Alert`, `RepairTask` in
// lib/types). Search, the scheduler and raw pages are still declared
// `list[dict[str, Any]]`, so the generated client types their rows as
// `Record<string, unknown>`; these mirror the SQL behind them
// (control.operator_search, control.operator_scheduler, sync.raw_page) until
// the API declares response models.

export type { Alert } from "@/lib/types";

interface SearchHit {
	account_id: string;
	account_name: string | null;
	connection_id: string;
	connector_id: string;
	created_at: string;
	environment_id: string;
	environment_slug: string;
	health_code: string | null;
	identifier: string | null;
	organization_id: string;
	organization_name: string | null;
	state: string;
	vendor_tenant_ref: string | null;
}

interface SchedulerRun {
	attempt: number;
	connection_id: string;
	connector_id: string;
	created_at: string;
	deadline_at: string | null;
	environment_id: string;
	error: unknown;
	health_code: string | null;
	mode: string;
	not_before: string | null;
	priority: number;
	run_id: string;
	state: string;
	stream: string;
	waiting_reason: string | null;
}

interface RawPageRow {
	bytes: number | null;
	connection_id: string;
	created_at: string;
	expires_at: string | null;
	id: string;
	request_summary: unknown;
	seq: number;
	stream: string;
	stream_run_id: string | null;
}

/** The untyped admin rows, as the shapes above (see the note there). */
function rowsAs<T>(rows: Record<string, unknown>[]): T[] {
	return rows as unknown as T[];
}

// ---------------------------------------------------------------------------
// Operator gate

/** Lets any tab drop the console into the gate when the API says 403
 * `operator_required` (for example, operator rights revoked mid-session). */
const DenyContext = createContext<() => void>(() => undefined);

/** A mutation `onError` that turns `operator_required` into the gate and
 * everything else into a toast. */
function useAdminError(title: string): (error: unknown) => void {
	const deny = useContext(DenyContext);
	return (error) => {
		if (isApiError(error, "operator_required")) {
			deny();
			return;
		}
		toast.error(title, { description: errorText(error) });
	};
}

export function OperatorRequired({ devMode }: { devMode: boolean }) {
	return (
		<EmptyState
			description={
				devMode
					? "You're using a development API key, and API keys can't be operators. Sign in with an operator account."
					: "Only SecureFabric operators can use this console. Ask an operator for access."
			}
			icon={<ShieldEllipsisIcon className="size-4" />}
			title="Operator access required"
		/>
	);
}

/** QueryState, except `operator_required` shows the gate, not an error. */
function AdminQueryState({
	query,
	children,
	empty,
	rows,
}: React.ComponentProps<typeof QueryState>) {
	const { devMode } = useEnv();
	if (isApiError(query.error, "operator_required")) {
		return <OperatorRequired devMode={devMode} />;
	}
	return (
		<QueryState empty={empty} query={query} rows={rows}>
			{children}
		</QueryState>
	);
}

// ---------------------------------------------------------------------------
// The view

const ADMIN_TABS = ["alerts", "search", "scheduler", "repairs"] as const;
type AdminTab = (typeof ADMIN_TABS)[number];

/**
 * The operator console (OPS-01/05/08, RAW-02): alerts, cross-account search,
 * the scheduler and connection repairs. Every endpoint is operator-only; an
 * API key (dev mode included) is never an operator, so it gets the gate.
 */
export function AdminView() {
	const { me, devMode } = useEnv();
	const [denied, setDenied] = useState(false);
	const [tab, setTab] = useSearchParam<AdminTab>("tab", ADMIN_TABS, "alerts");
	const allowed = me.is_operator && !denied;
	return (
		<>
			<PageHeader
				description="Support tools for SecureFabric operators. Every customer access needs a reason and is audited."
				title="Operator console"
			>
				{allowed ? (
					<Tabs
						className="px-4 sm:px-6"
						onChange={setTab}
						tabs={[
							{ label: "Alerts", value: "alerts" },
							{ label: "Search", value: "search" },
							{ label: "Scheduler", value: "scheduler" },
							{ label: "Repairs", value: "repairs" },
						]}
						value={tab}
					/>
				) : null}
			</PageHeader>
			<PageBody>
				{allowed ? (
					<DenyContext value={() => setDenied(true)}>
						{tab === "alerts" ? <AlertsTab /> : null}
						{tab === "search" ? <SearchTab /> : null}
						{tab === "scheduler" ? <SchedulerTab /> : null}
						{tab === "repairs" ? <RepairsFromUrl /> : null}
					</DenyContext>
				) : (
					<OperatorRequired devMode={devMode} />
				)}
			</PageBody>
		</>
	);
}

/** Where a search result or scheduler row sends you to repair a connection. */
function useRepairHref(): (
	environmentId: string,
	connectionId: string
) => string {
	const href = useHref();
	return (environmentId, connectionId) =>
		href(
			`/admin?${new URLSearchParams({
				connection: connectionId,
				environment: environmentId,
				tab: "repairs",
			})}`
		);
}

// ---------------------------------------------------------------------------
// Alerts

/** `AlertOut.severity` is page | ticket | info (a plain string in the schema). */
const SEVERITY_TONES: Record<string, Tone> = {
	info: "neutral",
	page: "error",
	ticket: "warn",
};

export function AlertsTab() {
	const { client } = useEnv();
	const [includeResolved, setIncludeResolved] = useState(false);
	const [resolving, setResolving] = useState<Alert | null>(null);
	const toggleId = useId();
	const alerts = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/admin/alerts", {
					params: { query: { include_resolved: includeResolved } },
				})
			),
		queryKey: ["admin", "alerts", includeResolved],
		refetchInterval: 30_000,
	});
	const rows = alerts.data ?? [];
	return (
		<Section
			action={
				<div className="flex items-center gap-2">
					<label
						className="text-muted-foreground flex items-center gap-2 text-sm"
						htmlFor={toggleId}
					>
						<Switch
							checked={includeResolved}
							id={toggleId}
							onChange={setIncludeResolved}
						/>
						Include resolved
					</label>
					<Button
						aria-label="Refresh alerts"
						onClick={() => alerts.refetch()}
						size="icon-sm"
						variant="ghost"
					>
						<RefreshCwIcon />
					</Button>
				</div>
			}
			description="Follow each alert's runbook, then resolve it with a note."
			title={includeResolved ? "All alerts" : "Open alerts"}
		>
			<AdminQueryState
				empty={{
					description: includeResolved
						? "No alerts have been raised yet."
						: "New alerts show up here.",
					title: includeResolved ? "No alerts" : "No open alerts",
					when: rows.length === 0,
				}}
				query={alerts}
			>
				<Card className="overflow-x-auto">
					<Table>
						<thead>
							<Tr>
								<Th>Severity</Th>
								<Th>Alert</Th>
								<Th>Raised</Th>
								<Th>Runbook</Th>
								<Th className="text-right">Status</Th>
							</Tr>
						</thead>
						<tbody>
							{rows.map((a) => (
								<AlertRow alert={a} key={a.id} onResolve={setResolving} />
							))}
						</tbody>
					</Table>
				</Card>
			</AdminQueryState>
			<ResolveDialog alert={resolving} onClose={() => setResolving(null)} />
		</Section>
	);
}

/** `detail.resolution`, written by POST …/resolve as `{ by, note }`. */
function resolutionOf(alert: Alert): { by?: string; note?: string } {
	const r = alert.detail.resolution;
	if (typeof r !== "object" || r === null) {
		return {};
	}
	const { by, note } = r as Record<string, unknown>;
	return {
		by: typeof by === "string" ? by : undefined,
		note: typeof note === "string" ? note : undefined,
	};
}

function AlertRow({
	alert,
	onResolve,
}: {
	alert: Alert;
	onResolve: (alert: Alert) => void;
}) {
	const resolution = resolutionOf(alert);
	return (
		<Tr data-alert-id={alert.id}>
			<Td>
				<Badge tone={SEVERITY_TONES[alert.severity] ?? "neutral"}>
					{enumLabel(alert.severity)}
				</Badge>
			</Td>
			<Td>
				<div className="grid min-w-0 gap-0.5">
					<span className="font-medium">{alert.name}</span>
					{alert.subject ? (
						<span className="text-muted-foreground truncate text-xs">
							{alert.subject}
						</span>
					) : null}
				</div>
			</Td>
			<Td className="text-xs">
				<When value={alert.raised_at} />
			</Td>
			<Td>
				{alert.runbook ? (
					<span className="inline-flex items-center gap-1">
						<Mono className="text-xs">{alert.runbook}</Mono>
						<CopyButton label="Runbook path" value={alert.runbook} />
					</span>
				) : (
					<span className="text-muted-foreground">—</span>
				)}
			</Td>
			<Td className="text-right">
				{alert.resolved_at ? (
					<div className="grid justify-items-end gap-0.5 text-xs">
						<span className="inline-flex items-center gap-1">
							<Badge tone="ok">Resolved</Badge>
							<When value={alert.resolved_at} />
						</span>
						{resolution.note ? (
							<span className="text-muted-foreground max-w-64 truncate">
								{resolution.note}
								{resolution.by ? ` · ${resolution.by}` : ""}
							</span>
						) : null}
					</div>
				) : (
					<Button onClick={() => onResolve(alert)} size="sm">
						<CheckIcon /> Resolve
					</Button>
				)}
			</Td>
		</Tr>
	);
}

const NOTE_MAX = 500;

function ResolveDialog({
	alert,
	onClose,
}: {
	alert: Alert | null;
	onClose: () => void;
}) {
	const { client } = useEnv();
	const queryClient = useQueryClient();
	const [note, setNote] = useState("");
	const noteId = useId();
	const onError = useAdminError("Couldn't resolve the alert");
	const resolve = useMutation({
		mutationFn: (vars: { id: string; note: string }) =>
			unwrap(
				client.POST("/v1/admin/alerts/{alert_id}/resolve", {
					body: { note: vars.note },
					params: { path: { alert_id: vars.id } },
				})
			),
		onError,
		onSuccess: async () => {
			toast.success("Alert resolved");
			setNote("");
			onClose();
			await queryClient.invalidateQueries({ queryKey: ["admin", "alerts"] });
		},
	});
	const trimmed = note.trim();
	const submit = (): void => {
		if (alert && trimmed) {
			resolve.mutate({ id: alert.id, note: trimmed });
		}
	};
	return (
		<Dialog
			onOpenChange={(open) => {
				if (!open) {
					onClose();
				}
			}}
			open={alert !== null}
		>
			<DialogContent
				description={
					alert
						? `${alert.name}${alert.subject ? ` · ${alert.subject}` : ""}`
						: undefined
				}
				footer={
					<>
						<Button onClick={onClose}>Cancel</Button>
						<Button
							disabled={!trimmed || resolve.isPending}
							onClick={submit}
							variant="primary"
						>
							Resolve alert
						</Button>
					</>
				}
				title="Resolve alert"
			>
				<Field
					help={`What you did. Saved with the alert (${note.length}/${NOTE_MAX}).`}
					htmlFor={noteId}
					label="Note"
				>
					<Textarea
						autoFocus
						id={noteId}
						maxLength={NOTE_MAX}
						onChange={(e) => setNote(e.target.value)}
						placeholder="Re-probed after the customer rotated credentials."
						value={note}
					/>
				</Field>
			</DialogContent>
		</Dialog>
	);
}

// ---------------------------------------------------------------------------
// Search

function SearchTab() {
	const { client } = useEnv();
	const repairHref = useRepairHref();
	const [draft, setDraft] = useState("");
	const [q, setQ] = useState("");
	const results = useQuery({
		enabled: q.length > 0,
		queryFn: () =>
			unwrap(client.GET("/v1/admin/search", { params: { query: { q } } })).then(
				rowsAs<SearchHit>
			),
		queryKey: ["admin", "search", q],
	});
	const rows = results.data ?? [];
	return (
		<Section
			description="Search by name, ID or vendor tenant. Shows up to 200 matches."
			title="Find a connection"
		>
			<form
				className="flex max-w-xl gap-2"
				onSubmit={(e) => {
					e.preventDefault();
					setQ(draft.trim());
				}}
			>
				<Input
					aria-label="Search"
					onChange={(e) => setDraft(e.target.value)}
					placeholder="acme, 0193…, github-org-name"
					value={draft}
				/>
				<Button disabled={!draft.trim()} type="submit" variant="primary">
					<SearchIcon /> Search
				</Button>
			</form>
			{q ? (
				<AdminQueryState
					empty={{
						description: `No connections match “${q}”.`,
						title: "No matches",
						when: rows.length === 0,
					}}
					query={results}
				>
					<Card className="overflow-x-auto">
						<Table>
							<thead>
								<Tr>
									<Th>Connection</Th>
									<Th>Account</Th>
									<Th>Organization</Th>
									<Th>Environment</Th>
									<Th>State</Th>
									<Th>Health</Th>
									<Th className="text-right">Actions</Th>
								</Tr>
							</thead>
							<tbody>
								{rows.map((r) => (
									<Tr key={r.connection_id}>
										<Td>
											<div className="grid gap-0.5">
												<span className="font-medium">
													{r.identifier ??
														r.vendor_tenant_ref ??
														r.connector_id}
												</span>
												<Mono className="text-muted-foreground text-xs">
													{r.connector_id} · {r.connection_id.slice(0, 8)}
												</Mono>
											</div>
										</Td>
										<Td className="text-xs">
											{r.account_name ?? r.account_id}
										</Td>
										<Td className="text-xs">
											{r.organization_name ?? r.organization_id}
										</Td>
										<Td>
											<Mono className="text-xs">{r.environment_slug}</Mono>
										</Td>
										<Td>
											<StatusBadge tones={STATE_TONES} value={r.state} />
										</Td>
										<Td>
											{r.health_code ? (
												<HealthBadge health={r.health_code} />
											) : (
												<span className="text-muted-foreground">—</span>
											)}
										</Td>
										<Td className="text-right">
											<Button
												render={
													<Link
														href={repairHref(r.environment_id, r.connection_id)}
													/>
												}
												size="sm"
											>
												<WrenchIcon /> Repair
											</Button>
										</Td>
									</Tr>
								))}
							</tbody>
						</Table>
					</Card>
				</AdminQueryState>
			) : null}
		</Section>
	);
}

// ---------------------------------------------------------------------------
// Scheduler

const SCHEDULER_STATES = [
	"QUEUED",
	"ADMITTED",
	"RUNNING",
	"PARKED",
	"RETRY_WAIT",
] as const;

function SchedulerTab() {
	const { client } = useEnv();
	const repairHref = useRepairHref();
	const runs = useQuery({
		queryFn: () =>
			unwrap(client.GET("/v1/admin/scheduler")).then(rowsAs<SchedulerRun>),
		queryKey: ["admin", "scheduler"],
		refetchInterval: 10_000,
	});
	const rows = runs.data ?? [];
	const counts = new Map<string, number>();
	for (const r of rows) {
		counts.set(r.state, (counts.get(r.state) ?? 0) + 1);
	}
	return (
		<Section
			action={
				<Button
					aria-label="Refresh scheduler"
					onClick={() => runs.refetch()}
					size="icon-sm"
					variant="ghost"
				>
					<RefreshCwIcon />
				</Button>
			}
			description="Active stream runs, by priority then age (up to 1,000). Refreshes every 10 seconds."
			title="Scheduler"
		>
			<AdminQueryState
				empty={{
					description: "Queued and running stream runs show up here.",
					title: "Scheduler is idle",
					when: rows.length === 0,
				}}
				query={runs}
			>
				<div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
					{SCHEDULER_STATES.map((s) => (
						<Card className="grid gap-1 p-4" key={s}>
							<span className="text-muted-foreground text-xs">
								{enumLabel(s)}
							</span>
							<span className="text-2xl font-semibold tabular-nums">
								{num(counts.get(s) ?? 0)}
							</span>
						</Card>
					))}
				</div>
				<Card className="overflow-x-auto">
					<Table>
						<thead>
							<Tr>
								<Th>State</Th>
								<Th>Connector · stream</Th>
								<Th>Mode</Th>
								<Th className="text-right">Priority</Th>
								<Th className="text-right">Attempt</Th>
								<Th>Waiting on</Th>
								<Th>Created</Th>
								<Th className="text-right">Connection</Th>
							</Tr>
						</thead>
						<tbody>
							{rows.map((r) => (
								<Tr key={r.run_id}>
									<Td>
										<StatusBadge tones={RUN_TONES} value={r.state} />
									</Td>
									<Td>
										<Mono className="text-xs">
											{r.connector_id} · {r.stream}
										</Mono>
									</Td>
									<Td className="text-xs">{r.mode}</Td>
									<Td className="text-right tabular-nums">{r.priority}</Td>
									<Td className="text-right tabular-nums">{r.attempt}</Td>
									<Td className="text-muted-foreground max-w-80 text-xs">
										{r.waiting_reason ?? "—"}
									</Td>
									<Td className="text-xs">
										<When value={r.created_at} />
									</Td>
									<Td className="text-right">
										<Link
											className="font-mono text-xs hover:underline"
											href={repairHref(r.environment_id, r.connection_id)}
										>
											{r.connection_id.slice(0, 8)}
										</Link>
									</Td>
								</Tr>
							))}
						</tbody>
					</Table>
				</Card>
			</AdminQueryState>
		</Section>
	);
}

// ---------------------------------------------------------------------------
// Repairs

/** What each repair does. Keyed by the API's enum, so a new action fails
 * the typecheck until it's described here. `queued` repairs run in the control
 * worker and answer `{ task_id }`, which GET /v1/admin/repairs/{task_id} follows. */
const REPAIR_INFO: Record<
	RepairAction,
	{ description: string; destructive?: boolean; queued?: boolean }
> = {
	pause: { description: "Stop scheduled syncs" },
	purge_now: {
		description: "Purge a deleted connection's data now",
		destructive: true,
		queued: true,
	},
	rebuild_counts: { description: "Recount live and deleted rows per stream" },
	renormalize: {
		description: "Re-run normalization for one stream from raw pages",
		queued: true,
	},
	reprobe: {
		description: "Re-verify credentials with the vendor",
		queued: true,
	},
	reset: {
		description: "Drop cursors and resync from scratch",
		destructive: true,
	},
	resume: { description: "Resume scheduled syncs" },
	trigger: { description: "Queue an on-demand sync now" },
};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
/** The API's floor for X-Support-Reason (`support_reason_required`). */
const REASON_MIN = 5;

/** The API's ceiling for X-Support-Reason. */
const REASON_MAX = 500;

/** Repairs, prefilled from `?environment=&connection=` (search links). Keyed
 * so following another link starts a fresh form. */
function RepairsFromUrl() {
	const params = useSearchParams();
	const environment = params.get("environment") ?? "";
	const connection = params.get("connection") ?? "";
	return (
		<RepairsTab
			initialConnectionId={connection}
			initialEnvironmentId={environment}
			key={`${environment}/${connection}`}
		/>
	);
}

interface RepairResult {
	action: RepairAction;
	at: number;
	connectionId: string;
	result: unknown;
	/** Set for queued repairs: the control task to follow. */
	taskId: string | null;
}

function taskIdOf(result: Record<string, unknown>): string | null {
	return typeof result.task_id === "string" ? result.task_id : null;
}

export function RepairsTab({
	initialEnvironmentId = "",
	initialConnectionId = "",
}: {
	initialEnvironmentId?: string;
	initialConnectionId?: string;
}) {
	const { client } = useEnv();
	const ids = {
		action: useId(),
		connection: useId(),
		environment: useId(),
		reason: useId(),
		stream: useId(),
		wipe: useId(),
	};
	const [environmentId, setEnvironmentId] = useState(initialEnvironmentId);
	const [connectionId, setConnectionId] = useState(initialConnectionId);
	const [action, setAction] = useState<RepairAction>("trigger");
	const [reason, setReason] = useState("");
	const [wipe, setWipe] = useState(false);
	const [stream, setStream] = useState("");
	const [last, setLast] = useState<RepairResult | null>(null);
	const [streamError, setStreamError] = useState<string | null>(null);
	const onAdminError = useAdminError(`Couldn't run ${action}`);
	const onError = (error: unknown): void => {
		// 422 stream_required belongs under the Stream field, not in a toast.
		if (isApiError(error, "stream_required")) {
			setStreamError(error.fieldErrors["params.stream"] ?? error.message);
			return;
		}
		onAdminError(error);
	};

	const env = environmentId.trim();
	const conn = connectionId.trim();
	const why = reason.trim();
	const problems = [
		UUID.test(env) ? null : "an environment ID",
		UUID.test(conn) ? null : "a connection ID",
		why.length >= REASON_MIN
			? null
			: `a support reason (at least ${REASON_MIN} characters)`,
		action === "renormalize" && !stream.trim() ? "a stream" : null,
	].filter((p): p is string => p !== null);

	const repair = useMutation({
		mutationFn: (vars: {
			action: RepairAction;
			connectionId: string;
			environmentId: string;
			params: Record<string, unknown>;
			reason: string;
		}) =>
			unwrap(
				client.POST(
					"/v1/admin/environments/{environment_id}/connections/{connection_id}/{action}",
					{
						body: { params: vars.params },
						params: {
							header: { "X-Support-Reason": vars.reason },
							path: {
								action: vars.action,
								connection_id: vars.connectionId,
								environment_id: vars.environmentId,
							},
						},
					}
				)
			),
		onError,
		onSuccess: (result, vars) => {
			toast.success(`${vars.action} sent`);
			setLast({
				action: vars.action,
				at: Date.now(),
				connectionId: vars.connectionId,
				result,
				taskId: REPAIR_INFO[vars.action].queued ? taskIdOf(result) : null,
			});
		},
	});

	const run = (): void => {
		setStreamError(null);
		const params: Record<string, unknown> = {};
		if (action === "reset" && wipe) {
			params.wipe = true;
		}
		if (action === "renormalize") {
			params.stream = stream.trim();
		}
		repair.mutate({
			action,
			connectionId: conn,
			environmentId: env,
			params,
			reason: why,
		});
	};

	const disabled = problems.length > 0 || repair.isPending;
	const label = `Run ${action}`;

	return (
		<div className="grid gap-8">
			<Section
				description="Runs with write access in the customer's environment. Your reason goes in their audit log."
				title="Repair a connection"
			>
				<Card className="grid gap-5 p-5">
					<div className="grid gap-4 sm:grid-cols-2">
						<Field htmlFor={ids.environment} label="Environment ID">
							<Input
								className="font-mono"
								id={ids.environment}
								onChange={(e) => setEnvironmentId(e.target.value)}
								placeholder="00000000-0000-0000-0000-000000000000"
								value={environmentId}
							/>
						</Field>
						<Field htmlFor={ids.connection} label="Connection ID">
							<Input
								className="font-mono"
								id={ids.connection}
								onChange={(e) => setConnectionId(e.target.value)}
								placeholder="00000000-0000-0000-0000-000000000000"
								value={connectionId}
							/>
						</Field>
					</div>
					<ActionPicker
						name={ids.action}
						onChange={(value) => {
							setAction(value);
							setStreamError(null);
						}}
						value={action}
					/>
					{action === "reset" ? (
						<label
							className="flex items-start gap-3 text-sm"
							htmlFor={ids.wipe}
						>
							<Switch checked={wipe} id={ids.wipe} onChange={setWipe} />
							<span className="grid gap-0.5">
								<span className="font-medium">Wipe data first</span>
								<span className="text-muted-foreground text-xs">
									Deletes the connection's rows before the resync. They come
									back only as the sync re-reads them.
								</span>
							</span>
						</label>
					) : null}
					{action === "renormalize" ? (
						<Field
							help={
								streamError ? (
									<span className="text-destructive" role="alert">
										{streamError}
									</span>
								) : (
									"The stream to re-normalize from its stored raw pages."
								)
							}
							htmlFor={ids.stream}
							label="Stream"
						>
							<Input
								aria-invalid={streamError ? true : undefined}
								className="max-w-sm font-mono"
								id={ids.stream}
								onChange={(e) => {
									setStream(e.target.value);
									setStreamError(null);
								}}
								placeholder="findings"
								value={stream}
							/>
						</Field>
					) : null}
					<Field
						help={`${REASON_MIN}–${REASON_MAX} characters. Recorded in the customer's audit log.`}
						htmlFor={ids.reason}
						label="Support reason"
					>
						<Textarea
							id={ids.reason}
							maxLength={REASON_MAX}
							onChange={(e) => setReason(e.target.value)}
							placeholder="Ticket #4821: customer reports findings stuck since Tuesday"
							value={reason}
						/>
					</Field>
					<div className="flex flex-wrap items-center justify-end gap-3">
						{problems.length ? (
							<span className="text-muted-foreground text-xs">
								Needs {problems.join(", ")}.
							</span>
						) : null}
						{REPAIR_INFO[action].destructive ? (
							<ConfirmButton
								confirmLabel={label}
								description={
									action === "reset"
										? `Resyncs connection ${conn} from scratch${wipe ? " after deleting its rows" : ""}. This can't be undone.`
										: `Purges connection ${conn}'s data now instead of at the end of its retention window. This can't be undone.`
								}
								disabled={disabled}
								onConfirm={run}
								size="sm"
								title={`${action} this connection?`}
							>
								<WrenchIcon /> {label}
							</ConfirmButton>
						) : (
							<Button disabled={disabled} onClick={run} variant="primary">
								<WrenchIcon /> {label}
							</Button>
						)}
					</div>
				</Card>
			</Section>
			{last ? <RepairResultSection last={last} /> : null}
			<RawPages connectionId={conn} environmentId={env} reason={why} />
		</div>
	);
}

function ActionPicker({
	name,
	value: action,
	onChange,
}: {
	name: string;
	value: RepairAction;
	onChange: (value: RepairAction) => void;
}) {
	return (
		<fieldset className="grid gap-1.5">
			<legend className="mb-1.5 text-sm font-medium">Action</legend>
			<div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
				{REPAIR_ACTIONS.map((value) => {
					const on = value === action;
					const info = REPAIR_INFO[value];
					return (
						<label
							className={cn(
								"border-border hover:bg-muted/60 has-focus-visible:ring-ring/40 grid cursor-pointer gap-0.5 rounded-md border p-3 transition-colors has-focus-visible:ring-2",
								on && "border-foreground bg-muted/60"
							)}
							key={value}
						>
							<input
								checked={on}
								className="sr-only"
								name={name}
								onChange={() => onChange(value)}
								type="radio"
								value={value}
							/>
							<span className="flex items-center gap-1.5 font-mono text-xs font-medium">
								{value}
								{info.destructive ? (
									<Badge tone="error">Destructive</Badge>
								) : null}
							</span>
							<span className="text-muted-foreground text-xs">
								{info.description}
							</span>
						</label>
					);
				})}
			</div>
		</fieldset>
	);
}

function RepairResultSection({ last }: { last: RepairResult }) {
	return (
		<Section
			description={
				<>
					<Mono className="text-xs">{last.action}</Mono> on{" "}
					<Mono className="text-xs">{last.connectionId}</Mono> ·{" "}
					<When value={new Date(last.at).toISOString()} />
				</>
			}
			title="Result"
		>
			<JsonBlock value={last.result} />
			{last.taskId ? <RepairTaskStatus taskId={last.taskId} /> : null}
		</Section>
	);
}

const TASK_TONES: Record<string, Tone> = {
	cancelled: "neutral",
	completed: "ok",
	failed: "error",
	pending: "busy",
	running: "busy",
	sleeping: "busy",
};
const TERMINAL = new Set(["completed", "failed", "cancelled"]);
const POLL_MS = 2000;

/** A queued repair, polled every 2s until it completes, fails or is cancelled. */
function RepairTaskStatus({ taskId }: { taskId: string }) {
	const { client } = useEnv();
	const task = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/admin/repairs/{task_id}", {
					params: { path: { task_id: taskId } },
				})
			),
		queryKey: ["admin", "repair", taskId],
		refetchInterval: (query) =>
			query.state.data && TERMINAL.has(query.state.data.state)
				? false
				: POLL_MS,
	});
	return (
		<Card className="grid gap-3 p-4" data-repair-task={taskId}>
			<div className="flex flex-wrap items-center gap-2 text-sm">
				<span className="font-medium">Repair task</span>
				<Mono className="text-muted-foreground text-xs">{taskId}</Mono>
				{task.data ? (
					<Badge tone={TASK_TONES[task.data.state] ?? "neutral"}>
						{enumLabel(task.data.state)}
					</Badge>
				) : null}
			</div>
			<AdminQueryState query={task} rows={1}>
				{task.data ? <RepairTaskBody task={task.data} /> : null}
			</AdminQueryState>
		</Card>
	);
}

function RepairTaskBody({ task }: { task: RepairTask }) {
	if (task.failure) {
		const { name, message } = task.failure;
		return (
			<div className="text-destructive grid gap-0.5 text-sm" role="alert">
				<span className="font-mono font-medium">
					{typeof name === "string" ? name : "Failed"}
				</span>
				{typeof message === "string" ? <span>{message}</span> : null}
			</div>
		);
	}
	if (task.result) {
		return <JsonBlock value={task.result} />;
	}
	return (
		<p className="text-muted-foreground text-sm">
			{TERMINAL.has(task.state)
				? "Finished with no result."
				: "Running in the control worker…"}
		</p>
	);
}

// ---------------------------------------------------------------------------
// Raw pages (RAW-02)

/** The raw vendor pages of a connection. Each list and each page opened is
 * an audited support access, so nothing loads until asked. */
function RawPages({
	environmentId,
	connectionId,
	reason,
}: {
	environmentId: string;
	connectionId: string;
	reason: string;
}) {
	const { client } = useEnv();
	const [target, setTarget] = useState<{
		connectionId: string;
		environmentId: string;
		reason: string;
	} | null>(null);
	const [openId, setOpenId] = useState<string | null>(null);
	const ready =
		UUID.test(environmentId) &&
		UUID.test(connectionId) &&
		reason.length >= REASON_MIN;
	const pages = useQuery({
		enabled: target !== null,
		queryFn: () => {
			if (!target) {
				return [];
			}
			return unwrap(
				client.GET("/v1/admin/environments/{environment_id}/raw_pages", {
					params: {
						header: { "X-Support-Reason": target.reason },
						path: { environment_id: target.environmentId },
						query: { connectionId: target.connectionId },
					},
				})
			).then(rowsAs<RawPageRow>);
		},
		queryKey: ["admin", "raw_pages", target],
	});
	const page = useQuery({
		enabled: target !== null && openId !== null,
		queryFn: () => {
			if (!(target && openId)) {
				return {};
			}
			return unwrap(
				client.GET(
					"/v1/admin/environments/{environment_id}/raw_pages/{raw_page_id}",
					{
						params: {
							header: { "X-Support-Reason": target.reason },
							path: {
								environment_id: target.environmentId,
								raw_page_id: openId,
							},
						},
					}
				)
			);
		},
		queryKey: ["admin", "raw_page", target?.environmentId, openId],
		staleTime: Number.POSITIVE_INFINITY,
	});
	const rows = pages.data ?? [];
	return (
		<Section
			action={
				<Button
					disabled={!ready}
					onClick={() => setTarget({ connectionId, environmentId, reason })}
					size="sm"
				>
					<FileSearchIcon /> List raw pages
				</Button>
			}
			description="Redacted vendor responses, as stored before normalization. Uses the details above; every view is audited."
			title="Raw pages"
		>
			{target ? (
				<AdminQueryState
					empty={{
						description: "This connection has none stored. Raw pages expire.",
						title: "No raw pages",
						when: rows.length === 0,
					}}
					query={pages}
				>
					<Card className="overflow-x-auto">
						<Table>
							<thead>
								<Tr>
									<Th>Stream</Th>
									<Th className="text-right">Seq</Th>
									<Th className="text-right">Bytes</Th>
									<Th>Request</Th>
									<Th>Stored</Th>
									<Th>Expires</Th>
									<Th className="text-right" />
								</Tr>
							</thead>
							<tbody>
								{rows.map((r) => (
									<Tr key={r.id}>
										<Td>
											<Mono className="text-xs">{r.stream}</Mono>
										</Td>
										<Td className="text-right tabular-nums">{r.seq}</Td>
										<Td className="text-right tabular-nums">
											{r.bytes === null ? "—" : num(r.bytes)}
										</Td>
										<Td className="max-w-80 truncate font-mono text-xs">
											{typeof r.request_summary === "string"
												? r.request_summary
												: JSON.stringify(r.request_summary)}
										</Td>
										<Td className="text-xs">
											<When value={r.created_at} />
										</Td>
										<Td className="text-xs">
											<When value={r.expires_at} />
										</Td>
										<Td className="text-right">
											<Button onClick={() => setOpenId(r.id)} size="sm">
												View
											</Button>
										</Td>
									</Tr>
								))}
							</tbody>
						</Table>
					</Card>
				</AdminQueryState>
			) : null}
			<Dialog
				onOpenChange={(open) => {
					if (!open) {
						setOpenId(null);
					}
				}}
				open={openId !== null}
			>
				<DialogContent
					className="max-w-3xl"
					description={openId ?? undefined}
					title="Raw page"
				>
					<AdminQueryState query={page}>
						<JsonBlock className="max-h-[60svh]" value={page.data} />
					</AdminQueryState>
				</DialogContent>
			</Dialog>
		</Section>
	);
}
