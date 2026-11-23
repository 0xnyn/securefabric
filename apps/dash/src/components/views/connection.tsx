"use client";

import {
	ArrowLeftIcon,
	EllipsisIcon,
	FlaskConicalIcon,
	KeyRoundIcon,
	LinkIcon,
	PauseIcon,
	PlayIcon,
	RefreshCwIcon,
	ShieldOffIcon,
	TerminalIcon,
	Trash2Icon,
	TriangleAlertIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import {
	CopyField,
	HealthBadge,
	KeyValue,
	PageBody,
	ProviderLogo,
	Tabs,
	useCopy,
} from "@/components/common";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button, buttonVariants } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	Menu,
	MenuContent,
	MenuItem,
	MenuSeparator,
	MenuTrigger,
	Select,
} from "@/components/ui/overlay";
import {
	Badge,
	Card,
	CardHeader,
	Dot,
	EmptyState,
	Field,
	Input,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";
import {
	AUTH_LABELS,
	MODELS,
	type ModelKey,
	providerOrThrow,
} from "@/lib/catalog";
import { dateTime, duration, num, timeAgo } from "@/lib/format";
import { CONNECTION_TABS, type ConnectionTab } from "@/lib/nav";
import {
	createConnectSession,
	deleteConnection,
	setPaused,
	simulateHealth,
	triggerSync,
	updateConnectionSettings,
	updateCredentials,
} from "@/lib/store";
import {
	type Connection,
	FREQUENCY_LABELS,
	FREQUENCY_MS,
	HEALTH,
	type SyncFrequency,
	type SyncJob,
} from "@/lib/types";
import { useSearchParam } from "@/lib/use-search-param";
import { RecordsBrowser } from "./records";
import { ActivityRow } from "./shared";

type Tab = ConnectionTab;

const TAB_VALUES = CONNECTION_TABS.map((t) => t.value);

export function ConnectionView({ id }: { id: string }) {
	const { env } = useEnv();
	const href = useHref();
	const conn = env.connections.find((c) => c.id === id);
	if (!conn) {
		return (
			<PageBody>
				<EmptyState
					action={
						<Link className={buttonVariants()} href={href("/connections")}>
							Back to connections
						</Link>
					}
					description={`No connection ${id} in ${env.name}. It may have been deleted, or it belongs to another environment.`}
					title="Connection not found"
				/>
			</PageBody>
		);
	}
	return <ConnectionDetail conn={conn} />;
}

function ConnectionDetail({ conn }: { conn: Connection }) {
	const { env } = useEnv();
	const href = useHref();
	const [tab, setTab] = useSearchParam<Tab>("tab", TAB_VALUES, "overview");
	const [browseModel, setBrowseModel] = useState<ModelKey | undefined>();
	const [editingCreds, setEditingCreds] = useState(false);
	const provider = providerOrThrow(conn.provider);
	const integration = env.integrations.find((i) => i.id === conn.integrationId);
	const models = integration?.models ?? provider.models;
	const ops = env.operations.filter((o) => o.connectionId === conn.id);

	const browse = (m: ModelKey): void => {
		setBrowseModel(m);
		setTab("records");
	};

	return (
		<>
			<div className="border-border bg-background border-b">
				<div className="px-4 pt-6 sm:px-8">
					<Link
						className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-sm"
						href={href("/connections")}
					>
						<ArrowLeftIcon className="size-3.5" />
						Connections
					</Link>
					<div className="flex flex-col gap-4 py-6 md:flex-row md:items-center md:justify-between">
						<div className="flex min-w-0 items-center gap-4">
							<ProviderLogo provider={provider} size={48} />
							<div className="grid min-w-0 gap-1">
								<div className="flex flex-wrap items-center gap-2">
									<h1 className="tracking-heading truncate text-2xl font-semibold">
										{conn.customer.orgName}
									</h1>
									<HealthBadge health={conn.health} />
									{conn.sandbox ? (
										<Badge tone="accent">
											<FlaskConicalIcon className="size-3" />
											Sandbox
										</Badge>
									) : null}
								</div>
								<p className="text-muted-foreground truncate font-mono text-xs">
									{conn.id} · {conn.integrationId}
								</p>
							</div>
						</div>
						<HeaderActions conn={conn} />
					</div>
					<div>
						<Tabs
							onChange={setTab}
							tabs={[
								{ label: "Overview", value: "overview" },
								{ label: "Records", value: "records" },
								{ count: conn.jobs.length, label: "Sync jobs", value: "jobs" },
								{ label: "Authorization", value: "auth" },
								{ count: ops.length, label: "Logs", value: "logs" },
								{ label: "Settings", value: "settings" },
							]}
							value={tab}
						/>
					</div>
				</div>
			</div>
			<PageBody className="grid gap-6">
				{conn.health === "UNAUTHORIZED" ? (
					<UnauthorizedBanner
						conn={conn}
						onUpdate={() => setEditingCreds(true)}
					/>
				) : null}
				{tab === "overview" ? (
					<OverviewTab conn={conn} models={models} onBrowse={browse} />
				) : null}
				{tab === "records" ? (
					<RecordsBrowser
						conn={conn}
						initialModel={browseModel}
						key={browseModel}
						models={models}
					/>
				) : null}
				{tab === "jobs" ? <JobsTab jobs={conn.jobs} /> : null}
				{tab === "auth" ? (
					<AuthTab conn={conn} onUpdate={() => setEditingCreds(true)} />
				) : null}
				{tab === "logs" ? <LogsTab conn={conn} /> : null}
				{tab === "settings" ? <SettingsTab conn={conn} /> : null}
			</PageBody>
			<UpdateCredentialsDialog
				conn={conn}
				onOpenChange={setEditingCreds}
				open={editingCreds}
			/>
		</>
	);
}

function HeaderActions({ conn }: { conn: Connection }) {
	const { env } = useEnv();
	const href = useHref();
	const router = useRouter();
	const running = conn.jobs[0]?.status === "RUNNING";
	return (
		<div className="flex shrink-0 items-center gap-2">
			<Link
				className={buttonVariants()}
				href={href(`/playground?connection=${conn.id}`)}
			>
				<TerminalIcon />
				Query in playground
			</Link>
			<Button
				disabled={running || conn.paused}
				onClick={() => {
					triggerSync(env.slug, conn.id);
					toast.success("Sync started", {
						description:
							"Only records changed since the last sync are fetched.",
					});
				}}
				variant="primary"
			>
				<RefreshCwIcon className={running ? "animate-spin" : undefined} />
				{running ? "Syncing…" : "Sync now"}
			</Button>
			<Menu>
				<MenuTrigger
					aria-label="More actions"
					className={buttonVariants({ size: "icon" })}
				>
					<EllipsisIcon />
				</MenuTrigger>
				<MenuContent align="end" className="w-60">
					<MenuItem onClick={() => setPaused(env.slug, conn.id, !conn.paused)}>
						{conn.paused ? <PlayIcon /> : <PauseIcon />}
						{conn.paused ? "Resume syncs" : "Pause syncs"}
					</MenuItem>
					{!env.isProduction && conn.health === "UNAUTHORIZED" ? (
						<MenuItem
							onClick={() => simulateHealth(env.slug, conn.id, "HEALTHY")}
						>
							<KeyRoundIcon />
							Test: restore credentials
						</MenuItem>
					) : null}
					{!env.isProduction && conn.health !== "UNAUTHORIZED" ? (
						<MenuItem
							onClick={() => simulateHealth(env.slug, conn.id, "UNAUTHORIZED")}
						>
							<ShieldOffIcon />
							Test: revoke credentials
						</MenuItem>
					) : null}
					<MenuSeparator />
					<MenuItem
						className="text-destructive [&_svg]:text-destructive"
						onClick={() => {
							deleteConnection(env.slug, conn.id);
							toast.success("Connection deleted", {
								description: "Credentials were destroyed and syncs stopped.",
							});
							router.push(href("/connections"));
						}}
					>
						<Trash2Icon />
						Delete connection
					</MenuItem>
				</MenuContent>
			</Menu>
		</div>
	);
}

function UnauthorizedBanner({
	conn,
	onUpdate,
}: {
	conn: Connection;
	onUpdate: () => void;
}) {
	const { env } = useEnv();
	const [, copy] = useCopy();
	return (
		<div className="border-destructive/30 bg-destructive/5 flex flex-col gap-4 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
			<div className="flex gap-3">
				<TriangleAlertIcon className="text-destructive mt-0.5 size-4 shrink-0" />
				<div className="grid gap-1 text-sm">
					<p className="text-destructive font-medium">
						{providerOrThrow(conn.provider).name} rejected the stored
						credentials
					</p>
					<p className="text-muted-foreground">
						{HEALTH.UNAUTHORIZED.description} API reads keep returning the last
						synced data.
					</p>
				</div>
			</div>
			<div className="flex shrink-0 gap-2">
				<Button
					onClick={async () => {
						const session = await createConnectSession(
							env.slug,
							conn.customer,
							[conn.integrationId]
						);
						copy(session.url, "Reconnect link");
					}}
					size="sm"
				>
					<LinkIcon />
					Copy reconnect link
				</Button>
				<Button onClick={onUpdate} size="sm" variant="primary">
					Update credentials
				</Button>
			</div>
		</div>
	);
}

function nextSync(conn: Connection, frequency: SyncFrequency): string {
	if (conn.paused) {
		return "Paused";
	}
	if (!conn.lastSyncAt) {
		return "After the initial sync";
	}
	const next = conn.lastSyncAt + FREQUENCY_MS[frequency];
	return next < Date.now() ? "Queued" : timeAgo(next);
}

function OverviewTab({
	conn,
	models,
	onBrowse,
}: {
	conn: Connection;
	models: ModelKey[];
	onBrowse: (m: ModelKey) => void;
}) {
	const { env } = useEnv();
	const integration = env.integrations.find((i) => i.id === conn.integrationId);
	const frequency =
		conn.frequencyOverride ?? integration?.syncFrequency ?? "1h";
	const health = HEALTH[conn.health];
	const syncing = conn.health === "SYNCING" && !conn.lastSyncAt;
	return (
		<div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
			<div className="grid content-start gap-6">
				<Card>
					<CardHeader
						description="Normalized records this connection holds, by model."
						title="Synced data"
					/>
					<ul className="divide-border divide-y">
						{models.map((m) => (
							<li
								className="flex items-center justify-between gap-4 px-5 py-4"
								key={m}
							>
								<div className="grid gap-0.5">
									<span className="font-mono text-sm font-medium">
										{MODELS[m].name}
									</span>
									<span className="text-muted-foreground text-xs">
										{MODELS[m].description}
									</span>
								</div>
								<div className="flex shrink-0 items-center gap-4">
									<span className="text-right text-sm tabular-nums">
										{syncing ? "Syncing…" : num(conn.counts[m] ?? 0)}
									</span>
									<Button
										disabled={syncing}
										onClick={() => onBrowse(m)}
										size="sm"
									>
										Browse
									</Button>
								</div>
							</li>
						))}
						{models.length === 0 ? (
							<li className="text-muted-foreground px-5 py-4 text-sm">
								Write actions only.
							</li>
						) : null}
					</ul>
				</Card>
				<Card>
					<CardHeader title="Health" />
					<div className="grid gap-4 px-5 py-4 sm:grid-cols-[auto_1fr]">
						<HealthBadge health={conn.health} />
						<div className="grid gap-1 text-sm">
							<p>{health.description}</p>
							<p className="text-muted-foreground text-xs">
								Code <span className="font-mono">{conn.health}</span> ·
								Resolution owner: {health.owner}
							</p>
						</div>
					</div>
				</Card>
				<Card>
					<CardHeader
						description="Copied from the connect session. Filter connections by any of them."
						title="Tags"
					/>
					<div className="flex flex-wrap gap-2 px-5 py-4">
						{Object.entries(conn.tags).map(([k, v]) => (
							<span
								className="border-border text-2xs inline-flex items-center overflow-hidden rounded-md border font-mono"
								key={k}
							>
								<span className="bg-muted text-muted-foreground px-2 py-1">
									{k}
								</span>
								<span className="px-2 py-1">{v}</span>
							</span>
						))}
					</div>
				</Card>
			</div>
			<Card className="h-fit">
				<CardHeader title="Details" />
				<div className="grid gap-4 px-5 py-4">
					<div className="grid gap-1">
						<span className="text-muted-foreground text-xs">Connection ID</span>
						<CopyField label="Connection ID" value={conn.id} />
					</div>
					<KeyValue
						className="sm:grid-cols-1"
						items={[
							{
								label: "Integration",
								value: (
									<span className="text-code font-mono">
										{conn.integrationId}
									</span>
								),
							},
							{
								label: "End user ID",
								value: (
									<span className="text-code font-mono">
										{conn.customer.endUserId}
									</span>
								),
							},
							{ label: "Admin email", value: conn.customer.email },
							{
								label: "Sync frequency",
								value: `${FREQUENCY_LABELS[frequency]}${conn.frequencyOverride ? " (override)" : ""}`,
							},
							{
								label: "Last sync",
								value: conn.lastSyncAt
									? `${timeAgo(conn.lastSyncAt)} · ${dateTime(conn.lastSyncAt)}`
									: "Never",
							},
							{ label: "Next sync", value: nextSync(conn, frequency) },
							{ label: "Created", value: dateTime(conn.createdAt) },
						]}
					/>
				</div>
			</Card>
		</div>
	);
}

const JOB_TONES = {
	FAILED: "error",
	QUEUED: "neutral",
	RUNNING: "busy",
	SUCCESS: "ok",
} as const;

function JobsTab({ jobs }: { jobs: SyncJob[] }) {
	return (
		<Card className="overflow-hidden">
			<Table>
				<thead>
					<tr>
						<Th>Job</Th>
						<Th>Type</Th>
						<Th>Status</Th>
						<Th>Started</Th>
						<Th className="text-right">Duration</Th>
						<Th className="text-right">Added</Th>
						<Th className="text-right">Updated</Th>
						<Th className="text-right">Deleted</Th>
					</tr>
				</thead>
				<tbody>
					{jobs.map((j) => (
						<Tr key={j.id}>
							<Td className="text-code text-muted-foreground font-mono">
								{j.id}
							</Td>
							<Td>
								<Badge className="font-mono">{j.type}</Badge>
							</Td>
							<Td>
								<span className="inline-flex items-center gap-2 text-sm">
									<Dot tone={JOB_TONES[j.status]} />
									{j.status.toLowerCase()}
								</span>
								{j.failureReason ? (
									<p className="text-destructive mt-0.5 text-xs">
										{j.failureReason}
									</p>
								) : null}
							</Td>
							<Td
								className="text-muted-foreground whitespace-nowrap"
								title={dateTime(j.startedAt)}
							>
								{timeAgo(j.startedAt)}
							</Td>
							<Td className="text-right tabular-nums">
								{j.durationMs === null ? "—" : duration(j.durationMs)}
							</Td>
							<Td className="text-right tabular-nums">{num(j.added)}</Td>
							<Td className="text-right tabular-nums">{num(j.updated)}</Td>
							<Td className="text-right tabular-nums">{num(j.deleted)}</Td>
						</Tr>
					))}
				</tbody>
			</Table>
		</Card>
	);
}

function AuthTab({
	conn,
	onUpdate,
}: {
	conn: Connection;
	onUpdate: () => void;
}) {
	const provider = providerOrThrow(conn.provider);
	if (conn.sandbox) {
		return (
			<Card className="p-6">
				<div className="flex gap-4">
					<FlaskConicalIcon className="text-ds-accent mt-0.5 size-5 shrink-0" />
					<div className="grid gap-1 text-sm">
						<p className="font-medium">Sandbox credentials</p>
						<p className="text-muted-foreground max-w-xl">
							This connection reads from an SecureFabric-hosted {provider.name}{" "}
							sandbox. No secrets are stored. Syncs, webhooks, health checks and
							the API behave exactly as they do for a live connection, so you
							can move to real credentials without code changes.
						</p>
					</div>
				</div>
			</Card>
		);
	}
	return (
		<Card>
			<CardHeader
				action={
					<Button onClick={onUpdate} size="sm">
						Update credentials
					</Button>
				}
				description="Encrypted at rest with AES-256-GCM. Secrets are write-only: the API and the dashboard never show them again."
				title={AUTH_LABELS[provider.auth]}
			/>
			<Table>
				<tbody>
					{provider.fields.map((f) => (
						<Tr key={f.key}>
							<Td className="text-muted-foreground w-56">{f.label}</Td>
							<Td className="text-code font-mono">
								{conn.credentials[f.key] || "—"}
							</Td>
						</Tr>
					))}
				</tbody>
			</Table>
		</Card>
	);
}

function LogsTab({ conn }: { conn: Connection }) {
	const href = useHref();
	const ops = useEnv()
		.env.operations.filter((o) => o.connectionId === conn.id)
		.slice(0, 40);
	return (
		<Card>
			<CardHeader
				action={
					<Link
						className="text-muted-foreground hover:text-foreground text-sm"
						href={href(`/logs?connection=${conn.id}`)}
					>
						Open in Logs
					</Link>
				}
				title="Recent operations"
			/>
			<div className="divide-border divide-y">
				{ops.map((op) => (
					<ActivityRow key={op.id} op={op} />
				))}
			</div>
		</Card>
	);
}

function SettingsTab({ conn }: { conn: Connection }) {
	const { env } = useEnv();
	const integration = env.integrations.find((i) => i.id === conn.integrationId);
	const [webhook, setWebhook] = useState(conn.webhookOverride ?? "");
	return (
		<div className="grid max-w-3xl gap-6">
			<Card>
				<CardHeader
					description={`Defaults to the integration's schedule (${FREQUENCY_LABELS[integration?.syncFrequency ?? "1h"]}).`}
					title="Sync frequency"
				/>
				<div className="px-5 py-4 sm:w-80">
					<Select
						ariaLabel="Sync frequency"
						onChange={(v) => {
							updateConnectionSettings(env.slug, conn.id, {
								frequencyOverride:
									v === "default" ? null : (v as SyncFrequency),
							});
							toast.success("Sync frequency updated");
						}}
						options={[
							{ label: "Use integration default", value: "default" },
							...(Object.keys(FREQUENCY_LABELS) as SyncFrequency[]).map(
								(f) => ({ label: FREQUENCY_LABELS[f], value: f })
							),
						]}
						value={conn.frequencyOverride ?? "default"}
					/>
				</div>
			</Card>
			<Card>
				<CardHeader
					description="Send this connection's webhooks to a different URL, e.g. a regional deployment."
					title="Webhook URL override"
				/>
				<form
					className="flex flex-col gap-2 px-5 py-4 sm:flex-row"
					onSubmit={(e) => {
						e.preventDefault();
						updateConnectionSettings(env.slug, conn.id, {
							webhookOverride: webhook.trim() || null,
						});
						toast.success(
							webhook.trim()
								? "Webhook override saved"
								: "Webhook override removed"
						);
					}}
				>
					<Input
						aria-label="Webhook URL override"
						className="font-mono"
						onChange={(e) => setWebhook(e.target.value)}
						placeholder="https://eu.api.example.com/webhooks/securefabric"
						value={webhook}
					/>
					<Button type="submit">Save</Button>
				</form>
			</Card>
			<Card className="border-destructive/30">
				<CardHeader
					description="Destroys stored credentials and stops syncs immediately. Synced records are purged after 31 days."
					title="Delete connection"
				/>
				<DeleteRow conn={conn} />
			</Card>
		</div>
	);
}

function DeleteRow({ conn }: { conn: Connection }) {
	const { env } = useEnv();
	const href = useHref();
	const router = useRouter();
	return (
		<div className="flex justify-end px-5 py-4">
			<Button
				onClick={() => {
					deleteConnection(env.slug, conn.id);
					toast.success("Connection deleted");
					router.push(href("/connections"));
				}}
				variant="destructive"
			>
				<Trash2Icon />
				Delete connection
			</Button>
		</div>
	);
}

function UpdateCredentialsDialog({
	conn,
	open,
	onOpenChange,
}: {
	conn: Connection;
	open: boolean;
	onOpenChange: (open: boolean) => void;
}) {
	const { env } = useEnv();
	const provider = providerOrThrow(conn.provider);
	const [values, setValues] = useState<Record<string, string>>({});
	const complete = provider.fields.every(
		(f) => f.options || (values[f.key] ?? "").trim()
	);
	return (
		<Dialog onOpenChange={onOpenChange} open={open}>
			<DialogContent
				description="New credentials replace the stored ones after they validate. A sync starts right away."
				footer={
					<>
						<Button onClick={() => onOpenChange(false)}>Cancel</Button>
						<Button
							disabled={!complete}
							onClick={() => {
								const filled = { ...values };
								for (const f of provider.fields) {
									filled[f.key] = filled[f.key] ?? f.options?.[0]?.value ?? "";
								}
								updateCredentials(env.slug, conn.id, filled);
								onOpenChange(false);
								toast.success("Credentials updated", {
									description: "Validated and saved. Syncing now.",
								});
							}}
							variant="primary"
						>
							Validate and save
						</Button>
					</>
				}
				title={`Update ${provider.name} credentials`}
			>
				<div className="grid gap-4">
					{provider.fields.map((f) => (
						<Field
							help={f.help}
							htmlFor={`u-${f.key}`}
							key={f.key}
							label={f.label}
						>
							{f.options ? (
								<Select
									ariaLabel={f.label}
									onChange={(v) => setValues({ ...values, [f.key]: v })}
									options={f.options}
									value={values[f.key] ?? f.options[0]?.value ?? ""}
								/>
							) : (
								<Input
									autoComplete="off"
									className="font-mono"
									id={`u-${f.key}`}
									onChange={(e) =>
										setValues({ ...values, [f.key]: e.target.value })
									}
									placeholder={f.placeholder}
									type={f.secret ? "password" : "text"}
									value={values[f.key] ?? ""}
								/>
							)}
						</Field>
					))}
				</div>
			</DialogContent>
		</Dialog>
	);
}
