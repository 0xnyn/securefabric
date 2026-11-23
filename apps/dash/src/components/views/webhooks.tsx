"use client";

import { cn } from "@securefabric/ui/lib/utils";
import {
	ChevronRightIcon,
	CircleCheckIcon,
	CircleXIcon,
	ClockIcon,
	EllipsisIcon,
	PauseIcon,
	PlayIcon,
	PlusIcon,
	RefreshCwIcon,
	RotateCwIcon,
	SendIcon,
	Trash2Icon,
	WebhookIcon,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { CodeBlock, SecretRow, Tabs } from "@/components/common";
import { useEnv } from "@/components/shell/env-context";
import { Button, buttonVariants } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogContent,
	Menu,
	MenuContent,
	MenuItem,
	MenuSeparator,
	MenuTrigger,
	Select,
	SheetContent,
} from "@/components/ui/overlay";
import {
	Badge,
	Card,
	CardFooter,
	CardHeader,
	EmptyState,
	Field,
	Input,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";
import { clock, dateTime, duration, timeAgo } from "@/lib/format";
import {
	addWebhook,
	deliverWebhook,
	removeWebhook,
	rotateWebhookSecret,
	updateWebhook,
} from "@/lib/store";
import { WEBHOOK_EVENTS, type Webhook, type WebhookEvent } from "@/lib/types";
import {
	type Delivery,
	type DeliveryStatus,
	deliveriesFor,
	deliveryHeaders,
	type EndpointStats,
	EVENT_GROUPS,
	endpointStats,
	eventsIn,
	WEBHOOK_EVENT_INFO,
} from "@/lib/webhooks";

const VERIFY_SAMPLE = `import { verifyWebhook } from "@securefabric/sdk/webhooks";

export async function POST(req: Request) {
  const event = verifyWebhook(
    await req.text(),
    req.headers.get("x-securefabric-signature"),
    process.env.SECUREFABRIC_WEBHOOK_SECRET,
  ); // throws if the signature or timestamp is invalid

  if (event.type === "connection.sync.unauthorized") {
    await notifyCustomer(event.connection_id);
  }
  return new Response(null, { status: 204 });
}`;

const DEFAULT_EVENTS: WebhookEvent[] = [
	"connection.create.succeeded",
	"connection.sync.unauthorized",
	"connection.sync.succeeded",
	"connection.sync.failed",
];

const HTTPS = /^https:\/\/[^\s/]+\.[^\s]+/u;

function eventsLabel(events: WebhookEvent[]): string {
	if (events.length === WEBHOOK_EVENTS.length) {
		return "All events";
	}
	return `${events.length} ${events.length === 1 ? "event" : "events"}`;
}

/** Success rate as people read it: green when healthy, amber, then red. */
function RateBadge({ stats }: { stats: EndpointStats }) {
	if (stats.successRate === null) {
		return <span className="text-muted-foreground">No deliveries</span>;
	}
	const pct = stats.successRate * 100;
	let tone: "ok" | "warn" | "error" = "error";
	if (pct >= 99) {
		tone = "ok";
	} else if (pct >= 90) {
		tone = "warn";
	}
	return <Badge tone={tone}>{pct >= 99.95 ? "100" : pct.toFixed(1)}%</Badge>;
}

const STATUS_ICON: Record<DeliveryStatus, typeof CircleCheckIcon> = {
	failed: CircleXIcon,
	retrying: ClockIcon,
	succeeded: CircleCheckIcon,
};

const STATUS_TONE: Record<DeliveryStatus, string> = {
	failed: "text-destructive",
	retrying: "text-ds-warn",
	succeeded: "text-ds-success",
};

const STATUS_LABEL: Record<DeliveryStatus, string> = {
	failed: "Failed",
	retrying: "Retrying",
	succeeded: "Succeeded",
};

function StatusCode({ code }: { code: number | null }) {
	if (code === null) {
		return <Badge tone="error">Timeout</Badge>;
	}
	return (
		<Badge className="font-mono" tone={code < 300 ? "ok" : "error"}>
			{code}
		</Badge>
	);
}

// ---------------------------------------------------------------------------
// The section

/**
 * Webhooks, laid out the way Stripe and Svix do it: a table of endpoints
 * with their health at a glance, each opening into its deliveries, where
 * every attempt, its response and the exact payload can be inspected and
 * resent.
 */
export function WebhooksSection() {
	const { env } = useEnv();
	const [adding, setAdding] = useState(false);
	const [openId, setOpenId] = useState<string | null>(null);
	const open = env.webhooks.find((w) => w.id === openId) ?? null;
	return (
		<>
			<Card className="overflow-hidden">
				<CardHeader
					action={
						<Button onClick={() => setAdding(true)} size="sm" variant="primary">
							<PlusIcon />
							Add endpoint
						</Button>
					}
					description="SecureFabric POSTs signed events to these URLs. Failed deliveries retry with backoff for about 18 hours."
					title="Endpoints"
				/>
				{env.webhooks.length === 0 ? (
					<EmptyState
						action={
							<Button onClick={() => setAdding(true)}>
								<PlusIcon />
								Add endpoint
							</Button>
						}
						className="border-0"
						description="Get sync and connection events pushed to your app instead of polling."
						icon={<WebhookIcon className="size-4" />}
						title="No endpoints"
					/>
				) : (
					<EndpointTable onOpen={setOpenId} webhooks={env.webhooks} />
				)}
			</Card>
			<SigningSecret />
			<AddEndpointDialog
				onCreated={setOpenId}
				onOpenChange={setAdding}
				open={adding}
			/>
			<Dialog
				onOpenChange={(next) => {
					if (!next) {
						setOpenId(null);
					}
				}}
				open={open !== null}
			>
				{open ? (
					<EndpointSheet hook={open} onDeleted={() => setOpenId(null)} />
				) : null}
			</Dialog>
		</>
	);
}

function EndpointTable({
	webhooks,
	onOpen,
}: {
	webhooks: Webhook[];
	onOpen: (id: string) => void;
}) {
	const { env } = useEnv();
	return (
		<Table>
			<thead>
				<tr>
					<Th>Endpoint</Th>
					<Th className="hidden sm:table-cell">Status</Th>
					<Th className="hidden md:table-cell">Listening to</Th>
					<Th>Success, 7d</Th>
					<Th className="hidden lg:table-cell">Last delivery</Th>
					<Th className="w-8">
						<span className="sr-only">Open</span>
					</Th>
				</tr>
			</thead>
			<tbody>
				{webhooks.map((w) => {
					const stats = endpointStats(deliveriesFor(env, w));
					return (
						<Tr
							className="hover:bg-ds-shell cursor-pointer"
							key={w.id}
							onClick={() => onOpen(w.id)}
						>
							<Td className="max-w-0 min-w-56">
								<button
									className="grid w-full min-w-0 py-1 text-left"
									onClick={(e) => {
										e.stopPropagation();
										onOpen(w.id);
									}}
									type="button"
								>
									<span className="text-code truncate font-mono">{w.url}</span>
									{w.description ? (
										<span className="text-muted-foreground truncate text-xs">
											{w.description}
										</span>
									) : null}
								</button>
							</Td>
							<Td className="hidden sm:table-cell">
								{w.disabled ? (
									<Badge>Disabled</Badge>
								) : (
									<Badge tone="ok">Enabled</Badge>
								)}
							</Td>
							<Td className="text-muted-foreground hidden md:table-cell">
								{eventsLabel(w.events)}
							</Td>
							<Td>
								<RateBadge stats={stats} />
							</Td>
							<Td className="text-muted-foreground hidden lg:table-cell">
								{stats.last ? (
									<span className="flex items-center gap-1.5">
										<DeliveryIcon status={stats.last.status} />
										{timeAgo(stats.last.startedAt)}
									</span>
								) : (
									"Never"
								)}
							</Td>
							<Td>
								<ChevronRightIcon className="text-muted-foreground size-4" />
							</Td>
						</Tr>
					);
				})}
			</tbody>
		</Table>
	);
}

function DeliveryIcon({ status }: { status: DeliveryStatus }) {
	const Icon = STATUS_ICON[status];
	return (
		<Icon
			aria-label={STATUS_LABEL[status]}
			className={cn("size-3.5 shrink-0", STATUS_TONE[status])}
		/>
	);
}

function SigningSecret() {
	const { env } = useEnv();
	return (
		<Card>
			<CardHeader
				description="Every endpoint in this environment shares it. Verify the X-SecureFabric-Signature header before trusting a delivery."
				title="Signing secret"
			/>
			<div className="grid gap-4 px-5 py-4">
				<SecretRow
					help="Rotating keeps the old secret valid for 5 minutes so in-flight deliveries still verify."
					label="Signing secret"
					value={env.webhookSecret}
				/>
				<CodeBlock
					code={VERIFY_SAMPLE}
					title="app/webhooks/securefabric/route.ts"
				/>
			</div>
			<CardFooter>
				<span>HMAC-SHA256 over the timestamp and raw body</span>
				<Button
					onClick={() => {
						rotateWebhookSecret(env.slug);
						toast.success("Signing secret rotated");
					}}
					size="sm"
				>
					<RefreshCwIcon />
					Rotate
				</Button>
			</CardFooter>
		</Card>
	);
}

// ---------------------------------------------------------------------------
// Events

/** Events grouped by what they're about, each with what it means. */
function EventChecklist({
	value,
	onChange,
}: {
	value: WebhookEvent[];
	onChange: (events: WebhookEvent[]) => void;
}) {
	const all = value.length === WEBHOOK_EVENTS.length;
	return (
		<div className="border-border divide-border divide-y rounded-lg border">
			<label className="flex items-center gap-3 px-4 py-3 text-sm font-medium">
				<Checkbox
					checked={all}
					indeterminate={!all && value.length > 0}
					onCheckedChange={(on) => onChange(on ? [...WEBHOOK_EVENTS] : [])}
				/>
				All events
				<span className="text-muted-foreground ml-auto text-xs font-normal">
					{value.length} of {WEBHOOK_EVENTS.length}
				</span>
			</label>
			{EVENT_GROUPS.map((group) => (
				<div className="grid gap-1 px-4 py-3" key={group}>
					<p className="text-muted-foreground text-xs font-medium">{group}</p>
					{eventsIn(group).map((e) => (
						<label className="flex items-start gap-3 py-1.5" key={e}>
							<Checkbox
								checked={value.includes(e)}
								className="mt-0.5"
								onCheckedChange={(on) =>
									onChange(
										on
											? WEBHOOK_EVENTS.filter(
													(x) => x === e || value.includes(x)
												)
											: value.filter((x) => x !== e)
									)
								}
							/>
							<span className="grid gap-0.5">
								<span className="text-code font-mono">{e}</span>
								<span className="text-muted-foreground text-xs">
									{WEBHOOK_EVENT_INFO[e].description}
								</span>
							</span>
						</label>
					))}
				</div>
			))}
		</div>
	);
}

function AddEndpointDialog({
	open,
	onOpenChange,
	onCreated,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onCreated: (id: string) => void;
}) {
	const { env } = useEnv();
	const [url, setUrl] = useState("");
	const [description, setDescription] = useState("");
	const [events, setEvents] = useState<WebhookEvent[]>(DEFAULT_EVENTS);
	const valid = HTTPS.test(url.trim()) && events.length > 0;
	const close = (): void => {
		onOpenChange(false);
		setUrl("");
		setDescription("");
		setEvents(DEFAULT_EVENTS);
	};
	const create = async (): Promise<void> => {
		const id = await addWebhook(
			env.slug,
			url.trim(),
			events,
			description.trim()
		);
		toast.success("Endpoint added", {
			description: "Send it a test event to check it's reachable.",
		});
		close();
		onCreated(id);
	};
	return (
		<Dialog
			onOpenChange={(next) => (next ? onOpenChange(true) : close())}
			open={open}
		>
			<DialogContent
				className="max-w-xl"
				description={`Events from ${env.name} are POSTed here as JSON, signed with the environment's signing secret.`}
				footer={
					<>
						<Button onClick={close}>Cancel</Button>
						<Button disabled={!valid} onClick={create} variant="primary">
							Add endpoint
						</Button>
					</>
				}
				title="Add endpoint"
			>
				<form
					className="grid gap-4"
					onSubmit={(e) => {
						e.preventDefault();
						if (valid) {
							create();
						}
					}}
				>
					<Field
						help={
							url && !HTTPS.test(url.trim())
								? "Use a public HTTPS URL."
								: "Must be HTTPS and reachable from the internet."
						}
						htmlFor="wh-url"
						label="Endpoint URL"
					>
						<Input
							autoFocus
							className="font-mono"
							id="wh-url"
							onChange={(e) => setUrl(e.target.value)}
							placeholder="https://api.example.com/webhooks/securefabric"
							value={url}
						/>
					</Field>
					<Field htmlFor="wh-desc" label="Description">
						<Input
							id="wh-desc"
							onChange={(e) => setDescription(e.target.value)}
							placeholder="Optional, e.g. Alerts service"
							value={description}
						/>
					</Field>
					<Field label="Events to send">
						<EventChecklist onChange={setEvents} value={events} />
					</Field>
				</form>
			</DialogContent>
		</Dialog>
	);
}

// ---------------------------------------------------------------------------
// One endpoint

type SheetTab = "deliveries" | "events" | "testing" | "settings";

function EndpointSheet({
	hook,
	onDeleted,
}: {
	hook: Webhook;
	onDeleted: () => void;
}) {
	const { env } = useEnv();
	const [tab, setTab] = useState<SheetTab>("deliveries");
	const deliveries = deliveriesFor(env, hook);
	const stats = endpointStats(deliveries);
	return (
		<SheetContent
			actions={
				<Menu>
					<MenuTrigger
						aria-label="Endpoint actions"
						className={buttonVariants({ size: "icon-sm", variant: "ghost" })}
					>
						<EllipsisIcon />
					</MenuTrigger>
					<MenuContent align="end" className="w-52">
						<MenuItem
							onClick={() => {
								updateWebhook(env.slug, hook.id, { disabled: !hook.disabled });
								toast.success(
									hook.disabled ? "Endpoint enabled" : "Endpoint disabled"
								);
							}}
						>
							{hook.disabled ? <PlayIcon /> : <PauseIcon />}
							{hook.disabled ? "Enable endpoint" : "Disable endpoint"}
						</MenuItem>
						<MenuSeparator />
						<MenuItem
							className="text-destructive [&_svg]:text-destructive"
							onClick={() => {
								removeWebhook(env.slug, hook.id);
								toast.success("Endpoint deleted");
								onDeleted();
							}}
						>
							<Trash2Icon />
							Delete endpoint
						</MenuItem>
					</MenuContent>
				</Menu>
			}
			className="max-w-3xl"
			description={
				<span className="flex items-center gap-2">
					{hook.disabled ? (
						<Badge>Disabled</Badge>
					) : (
						<Badge tone="ok">Enabled</Badge>
					)}
					{hook.description || `Added ${timeAgo(hook.createdAt)}`}
				</span>
			}
			title={<span className="text-code font-mono">{hook.url}</span>}
		>
			<div className="border-border grid grid-cols-2 border-b sm:grid-cols-4">
				<Stat label="Success, 7d" value={<RateBadge stats={stats} />} />
				<Stat label="Deliveries, 7d" value={stats.total.toLocaleString()} />
				<Stat
					label="Failed or retrying"
					value={stats.failed.toLocaleString()}
				/>
				<Stat
					label="Avg response"
					value={stats.avgMs === null ? "—" : duration(stats.avgMs)}
				/>
			</div>
			<div className="px-6">
				<Tabs
					onChange={setTab}
					tabs={[
						{
							count: deliveries.length,
							label: "Deliveries",
							value: "deliveries",
						},
						{ count: hook.events.length, label: "Events", value: "events" },
						{ label: "Testing", value: "testing" },
						{ label: "Settings", value: "settings" },
					]}
					value={tab}
				/>
			</div>
			<div className="px-6 py-5">
				{tab === "deliveries" ? (
					<DeliveryList deliveries={deliveries} hook={hook} />
				) : null}
				{tab === "events" ? <EventsTab hook={hook} key={hook.id} /> : null}
				{tab === "testing" ? (
					<TestingTab hook={hook} onSent={() => setTab("deliveries")} />
				) : null}
				{tab === "settings" ? <SettingsTab hook={hook} key={hook.id} /> : null}
			</div>
		</SheetContent>
	);
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
	return (
		<div className="border-border grid gap-1 border-r px-6 py-4 last:border-r-0">
			<span className="text-muted-foreground text-xs">{label}</span>
			<span className="text-lg font-semibold tabular-nums">{value}</span>
		</div>
	);
}

type DeliveryFilter = "all" | "succeeded" | "failing";

const PAGE = 25;

function DeliveryList({
	deliveries,
	hook,
}: {
	deliveries: Delivery[];
	hook: Webhook;
}) {
	const [filter, setFilter] = useState<DeliveryFilter>("all");
	const [expanded, setExpanded] = useState<string | null>(null);
	const [limit, setLimit] = useState(PAGE);
	const visible = deliveries.filter((d) => {
		if (filter === "succeeded") {
			return d.status === "succeeded";
		}
		if (filter === "failing") {
			return d.status !== "succeeded";
		}
		return true;
	});
	return (
		<div className="grid gap-3">
			<div className="flex items-center justify-between gap-3">
				<div className="flex gap-1">
					{(
						[
							["all", "All"],
							["succeeded", "Succeeded"],
							["failing", "Failed or retrying"],
						] as const
					).map(([value, label]) => (
						<button
							aria-pressed={filter === value}
							className={cn(
								"h-7 rounded-md px-2.5 text-xs transition-colors",
								filter === value
									? "bg-muted text-foreground font-medium"
									: "text-muted-foreground hover:bg-muted/60"
							)}
							key={value}
							onClick={() => setFilter(value)}
							type="button"
						>
							{label}
						</button>
					))}
				</div>
				<span className="text-muted-foreground text-xs">
					{visible.length.toLocaleString()} deliveries
				</span>
			</div>
			{visible.length === 0 ? (
				<p className="text-muted-foreground py-8 text-center text-sm">
					{deliveries.length === 0
						? "Nothing delivered yet. Send a test event from the Testing tab."
						: "No deliveries match."}
				</p>
			) : (
				<ul className="border-border divide-border divide-y overflow-hidden rounded-lg border">
					{visible.slice(0, limit).map((d) => (
						<DeliveryRow
							delivery={d}
							hook={hook}
							key={d.id}
							onToggle={() => setExpanded(expanded === d.id ? null : d.id)}
							open={expanded === d.id}
						/>
					))}
				</ul>
			)}
			{visible.length > limit ? (
				<Button
					className="justify-self-center"
					onClick={() => setLimit(limit + PAGE)}
					size="sm"
				>
					Show more
				</Button>
			) : null}
		</div>
	);
}

function DeliveryRow({
	delivery,
	hook,
	open,
	onToggle,
}: {
	delivery: Delivery;
	hook: Webhook;
	open: boolean;
	onToggle: () => void;
}) {
	const last = delivery.attempts.at(-1);
	return (
		<li>
			<button
				aria-expanded={open}
				className="hover:bg-ds-shell flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors"
				onClick={onToggle}
				type="button"
			>
				<ChevronRightIcon
					className={cn(
						"text-muted-foreground size-3.5 shrink-0 transition-transform duration-150",
						open && "rotate-90"
					)}
				/>
				<DeliveryIcon status={delivery.status} />
				<span className="text-code min-w-0 flex-1 truncate font-mono">
					{delivery.event === "ping" ? "webhook.ping" : delivery.event}
					{delivery.customer ? (
						<span className="text-muted-foreground font-sans">
							{" "}
							· {delivery.customer}
						</span>
					) : null}
				</span>
				{delivery.attempts.length > 1 ? (
					<span className="text-muted-foreground hidden text-xs sm:inline">
						{delivery.attempts.length} attempts
					</span>
				) : null}
				<StatusCode code={last?.statusCode ?? null} />
				<span
					className="text-muted-foreground w-16 text-right text-xs tabular-nums"
					title={dateTime(delivery.startedAt)}
				>
					{timeAgo(delivery.startedAt)}
				</span>
			</button>
			{open ? <DeliveryDetail delivery={delivery} hook={hook} /> : null}
		</li>
	);
}

/** Every attempt, then the request exactly as sent and the response. */
function DeliveryDetail({
	delivery,
	hook,
}: {
	delivery: Delivery;
	hook: Webhook;
}) {
	const { env } = useEnv();
	const last = delivery.attempts.at(-1);
	const resend = (): void => {
		deliverWebhook(env.slug, hook.id, delivery.event, delivery.connectionId);
		toast.success("Event resent", {
			description: "200 OK. It's at the top of the list.",
		});
	};
	return (
		<div className="bg-ds-shell border-border grid gap-4 border-t px-4 py-4">
			<div className="flex flex-wrap items-center justify-between gap-2">
				<span className="text-muted-foreground font-mono text-xs">
					{delivery.id}
				</span>
				<Button onClick={resend} size="sm">
					<RotateCwIcon />
					Resend
				</Button>
			</div>
			{delivery.status === "retrying" && delivery.nextRetryAt ? (
				<p className="text-ds-warn-text text-xs">
					Next attempt at {clock(delivery.nextRetryAt)}. Resend to deliver it
					now.
				</p>
			) : null}
			{delivery.status === "failed" ? (
				<p className="text-destructive text-xs">
					Every scheduled attempt failed. Fix the endpoint, then resend.
				</p>
			) : null}
			<div className="grid gap-1.5">
				<p className="text-xs font-medium">Attempts</p>
				<ol className="border-border bg-card divide-border divide-y rounded-md border">
					{delivery.attempts.map((a, i) => (
						<li
							className="flex items-center gap-3 px-3 py-2 text-xs"
							key={a.at}
						>
							<span className="text-muted-foreground w-16">
								Attempt {i + 1}
							</span>
							<StatusCode code={a.statusCode} />
							<span className="text-muted-foreground min-w-0 flex-1 truncate">
								{a.error ??
									(a.statusCode && a.statusCode < 300
										? "Delivered"
										: a.response)}
							</span>
							<span className="text-muted-foreground tabular-nums">
								{duration(a.durationMs)}
							</span>
							<span className="text-muted-foreground w-20 text-right tabular-nums">
								{clock(a.at)}
							</span>
						</li>
					))}
				</ol>
			</div>
			<div className="grid gap-4 lg:grid-cols-2">
				<CodeBlock
					code={`POST ${hook.url}\n${Object.entries(deliveryHeaders(delivery))
						.map(([k, v]) => `${k}: ${v}`)
						.join("\n")}\n\n${JSON.stringify(delivery.payload, null, 2)}`}
					maxHeight="20rem"
					title="Request"
				/>
				<CodeBlock
					code={
						last?.statusCode
							? `HTTP ${last.statusCode}\n\n${last.response}`
							: (last?.error ?? "No response")
					}
					maxHeight="20rem"
					title="Response"
				/>
			</div>
		</div>
	);
}

function EventsTab({ hook }: { hook: Webhook }) {
	const { env } = useEnv();
	const [events, setEvents] = useState(hook.events);
	const dirty =
		events.length !== hook.events.length ||
		events.some((e) => !hook.events.includes(e));
	return (
		<div className="grid gap-4">
			<EventChecklist onChange={setEvents} value={events} />
			<div className="flex justify-end gap-2">
				<Button disabled={!dirty} onClick={() => setEvents(hook.events)}>
					Reset
				</Button>
				<Button
					disabled={!dirty || events.length === 0}
					onClick={() => {
						updateWebhook(env.slug, hook.id, { events });
						toast.success("Events saved");
					}}
					variant="primary"
				>
					Save events
				</Button>
			</div>
		</div>
	);
}

/** Send one event of any type, with a payload preview, without waiting for
 * a real sync or connection to produce one. */
function TestingTab({ hook, onSent }: { hook: Webhook; onSent: () => void }) {
	const { env } = useEnv();
	const [event, setEvent] = useState<WebhookEvent | "ping">("ping");
	const [conn] = env.connections;
	const example = {
		connection_id: event === "ping" ? null : (conn?.id ?? "conn_XXXXXXXXXXXX"),
		created_at: new Date().toISOString(),
		data:
			event === "ping"
				? { description: "Test event from the SecureFabric dashboard" }
				: {
						customer: conn?.customer.orgName ?? "Acme Corp",
						error:
							event === "connection.sync.unauthorized" ? "UNAUTHORIZED" : null,
						integration_id: conn?.integrationId ?? "tenable",
						vendor: conn?.provider ?? "tenable",
					},
		environment_id: env.id,
		id: "evt_test",
		type: event === "ping" ? "webhook.ping" : event,
	};
	return (
		<div className="grid gap-4">
			<div className="flex flex-col gap-2 sm:flex-row sm:items-end">
				<Field className="flex-1" label="Event">
					<Select
						ariaLabel="Event"
						onChange={setEvent}
						options={[
							{ label: "webhook.ping", value: "ping" as const },
							...WEBHOOK_EVENTS.map((e) => ({ label: e, value: e })),
						]}
						value={event}
					/>
				</Field>
				<Button
					disabled={hook.disabled}
					onClick={() => {
						deliverWebhook(
							env.slug,
							hook.id,
							event,
							event === "ping" ? null : (conn?.id ?? null)
						);
						toast.success("Test event delivered", { description: "200 OK" });
						onSent();
					}}
					variant="primary"
				>
					<SendIcon />
					Send test event
				</Button>
			</div>
			{hook.disabled ? (
				<p className="text-muted-foreground text-xs">
					Enable the endpoint to send it events.
				</p>
			) : null}
			<CodeBlock code={JSON.stringify(example, null, 2)} json title="Payload" />
		</div>
	);
}

function SettingsTab({ hook }: { hook: Webhook }) {
	const { env } = useEnv();
	const [url, setUrl] = useState(hook.url);
	const [description, setDescription] = useState(hook.description ?? "");
	const dirty = url !== hook.url || description !== (hook.description ?? "");
	return (
		<form
			className="grid max-w-xl gap-4"
			onSubmit={(e) => {
				e.preventDefault();
				if (!HTTPS.test(url.trim())) {
					toast.error("Use a public HTTPS URL");
					return;
				}
				updateWebhook(env.slug, hook.id, {
					description: description.trim(),
					url: url.trim(),
				});
				toast.success("Endpoint saved");
			}}
		>
			<Field htmlFor="wh-edit-url" label="Endpoint URL">
				<Input
					className="font-mono"
					id="wh-edit-url"
					onChange={(e) => setUrl(e.target.value)}
					value={url}
				/>
			</Field>
			<Field htmlFor="wh-edit-desc" label="Description">
				<Input
					id="wh-edit-desc"
					onChange={(e) => setDescription(e.target.value)}
					value={description}
				/>
			</Field>
			<div>
				<Button disabled={!dirty} type="submit" variant="primary">
					Save
				</Button>
			</div>
		</form>
	);
}
