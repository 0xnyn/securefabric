"use client";

import { unwrap } from "@securefabric/client";
import { Badge } from "@securefabric/ui/components/badge";
import { Button } from "@securefabric/ui/components/button";
import { Card } from "@securefabric/ui/components/card";
import {
	Dialog,
	DialogContent,
	SheetContent,
} from "@securefabric/ui/components/dialog";
import { Field, Input } from "@securefabric/ui/components/form";
import { Switch } from "@securefabric/ui/components/switch";
import { Table, Td, Th, Tr } from "@securefabric/ui/components/table";
import { Tooltip } from "@securefabric/ui/components/tooltip";
import { dateTime, plural } from "@securefabric/ui/lib/format";
import { CopyField } from "@securefabric/ui/patterns/copy";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { Section } from "@securefabric/ui/patterns/section";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { TriangleAlertIcon } from "lucide-react";
import { Fragment, useState } from "react";
import { toast } from "sonner";
import { Gated } from "@/components/domain/access";
import { ConfirmButton } from "@/components/domain/confirm-button";
import { JsonBlock } from "@/components/domain/json-block";
import { errorText, QueryState } from "@/components/domain/query-state";
import { When } from "@/components/domain/when";
import { useAccess, useEnv } from "@/components/shell/env-context";
import type { Requirement } from "@/lib/access";
import { DELIVERY_TONES, type WebhookEndpoint } from "@/lib/types";

export const EVENT_TYPES = [
	"action.completed",
	"action.failed",
	"connection.create.failed",
	"connection.create.succeeded",
	"connection.deleted",
	"connection.health.changed",
	"connection.paused",
	"connection.resumed",
	"connection.sync.failed",
	"connection.sync.succeeded",
	"connection.sync.unauthorized",
	"sync.completed",
] as const;

/** Each event type in words. The raw name stays beside it in mono. */
export const EVENT_LABELS: Record<string, string> = {
	"action.completed": "Write-back action completed",
	"action.failed": "Write-back action failed",
	"connection.create.failed": "Connection setup failed",
	"connection.create.succeeded": "Connection created",
	"connection.deleted": "Connection deleted",
	"connection.health.changed": "Connection health changed",
	"connection.paused": "Connection paused",
	"connection.resumed": "Connection resumed",
	"connection.sync.failed": "Sync failed",
	"connection.sync.succeeded": "Sync succeeded",
	"connection.sync.unauthorized": "Sync lost access",
	"sync.completed": "Sync completed",
	"webhook.ping": "Test ping",
};

export function eventLabel(type: string): string {
	return EVENT_LABELS[type] ?? type;
}

/** Delivery statuses in words (events/delivery.py). */
const DELIVERY_LABELS: Record<string, string> = {
	DEAD: "Gave up after retries",
	DELIVERED: "Delivered",
	FAILED: "Failed",
	PENDING: "Pending",
};

const MANAGE: Requirement = { scope: "webhooks:manage" };

const idem = () => ({ "Idempotency-Key": crypto.randomUUID() });

function hostOf(url: string): string {
	try {
		return new URL(url).host;
	} catch {
		return url;
	}
}

export function WebhooksView() {
	const { client, env } = useEnv();
	const queryClient = useQueryClient();
	const endpoints = useQuery({
		queryFn: () => unwrap(client.GET("/v1/webhook_endpoints")),
		queryKey: ["webhooks", env.id],
	});
	const [creating, setCreating] = useState(false);
	const [selected, setSelected] = useState<WebhookEndpoint | null>(null);
	const [secret, setSecret] = useState<string | null>(null);
	const refresh = () =>
		queryClient.invalidateQueries({ queryKey: ["webhooks", env.id] });
	const addButton = (size?: "sm") => (
		<Gated requires={MANAGE}>
			<Button onClick={() => setCreating(true)} size={size} variant="primary">
				Add endpoint
			</Button>
		</Gated>
	);
	return (
		<>
			<PageHeader
				actions={addButton()}
				description="Send signed events to your backend when connections, syncs and write-back actions change."
				title="Webhooks"
			/>
			<PageBody>
				<QueryState
					empty={{
						action: addButton("sm"),
						description:
							"Add an HTTPS endpoint to get events when connections and syncs change.",
						title: "No endpoints yet",
						when: (endpoints.data ?? []).length === 0,
					}}
					query={endpoints}
				>
					<Card>
						<Table>
							<thead>
								<Tr>
									<Th>Endpoint URL</Th>
									<Th>Events</Th>
									<Th>Status</Th>
									<Th>Secret</Th>
									<Th>Created</Th>
								</Tr>
							</thead>
							<tbody>
								{endpoints.data?.map((e) => (
									<Tr
										className="hover:bg-muted/40 cursor-pointer"
										key={e.id}
										onClick={() => setSelected(e)}
									>
										<Td className="max-w-sm truncate font-mono text-xs">
											{e.url}
										</Td>
										<Td>
											<EventCount types={e.event_types} />
										</Td>
										<Td>
											<EndpointStatus endpoint={e} />
										</Td>
										<Td className="font-mono text-xs">…{e.secret_hint}</Td>
										<Td>
											<When value={e.created_at} />
										</Td>
									</Tr>
								))}
							</tbody>
						</Table>
					</Card>
				</QueryState>
			</PageBody>
			<EndpointDialog
				onCreated={(s) => {
					setSecret(s);
					refresh();
				}}
				onOpenChange={setCreating}
				open={creating}
			/>
			<Dialog
				onOpenChange={(o) => (o ? null : setSecret(null))}
				open={secret !== null}
			>
				<DialogContent
					description="Use it to verify the SecureFabric-Signature header on each delivery."
					footer={
						<Button onClick={() => setSecret(null)} variant="primary">
							I've saved the secret
						</Button>
					}
					title="Copy your signing secret"
				>
					<div className="grid gap-4">
						<div
							className="border-ds-severity-high/40 bg-ds-severity-high/10 flex items-start gap-2 rounded-md border px-3 py-2 text-sm"
							role="alert"
						>
							<TriangleAlertIcon className="mt-0.5 size-4 shrink-0" />
							<span>
								<strong className="font-medium">Shown once.</strong> You can't
								see this secret again after you close this window.
							</span>
						</div>
						{secret ? (
							<CopyField label="Signing secret" value={secret} />
						) : null}
					</div>
				</DialogContent>
			</Dialog>
			<Dialog
				onOpenChange={(o) => (o ? null : setSelected(null))}
				open={selected !== null}
			>
				{selected ? (
					<EndpointSheet
						endpoint={selected}
						onChanged={refresh}
						onDeleted={() => {
							setSelected(null);
							refresh();
						}}
						onSecret={setSecret}
					/>
				) : null}
			</Dialog>
		</>
	);
}

/** "All events", or how many, with their names on hover. */
function EventCount({ types }: { types: string[] }) {
	if (types.length === 0) {
		return <span className="text-sm">All events</span>;
	}
	return (
		<Tooltip
			content={
				<ul className="grid gap-0.5">
					{types.map((t) => (
						<li key={t}>{eventLabel(t)}</li>
					))}
				</ul>
			}
		>
			<span className="text-sm">{plural(types.length, "event")}</span>
		</Tooltip>
	);
}

function EndpointStatus({ endpoint: e }: { endpoint: WebhookEndpoint }) {
	if (!e.enabled) {
		const badge = <Badge>Disabled</Badge>;
		return e.disabled_reason ? (
			<Tooltip content={`Disabled: ${e.disabled_reason}`}>{badge}</Tooltip>
		) : (
			badge
		);
	}
	return e.failing_since ? (
		<Tooltip
			content={`Failing since ${dateTime(new Date(e.failing_since).getTime())}`}
		>
			<Badge tone="warn">Failing</Badge>
		</Tooltip>
	) : (
		<span className="text-muted-foreground text-sm">Enabled</span>
	);
}

function EventPicker({
	value,
	onChange,
	disabled,
}: {
	value: string[];
	onChange: (v: string[]) => void;
	disabled?: boolean;
}) {
	return (
		<div className="grid gap-1.5 sm:grid-cols-2">
			{EVENT_TYPES.map((t) => (
				<label className="flex items-start gap-2 text-sm" key={t}>
					<input
						checked={value.includes(t)}
						className="mt-1"
						disabled={disabled}
						onChange={(e) =>
							onChange(
								e.target.checked ? [...value, t] : value.filter((x) => x !== t)
							)
						}
						type="checkbox"
					/>
					<span className="grid">
						<span>{eventLabel(t)}</span>
						<span className="text-muted-foreground font-mono text-xs">{t}</span>
					</span>
				</label>
			))}
		</div>
	);
}

function EndpointDialog({
	open,
	onOpenChange,
	onCreated,
}: {
	open: boolean;
	onOpenChange: (o: boolean) => void;
	onCreated: (secret: string) => void;
}) {
	const { client } = useEnv();
	const [url, setUrl] = useState("");
	const [description, setDescription] = useState("");
	const [types, setTypes] = useState<string[]>([]);
	const create = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/webhook_endpoints", {
					body: {
						description: description || null,
						enabled: true,
						event_types: types,
						url,
					},
					headers: idem(),
				})
			),
		onError: (e) =>
			toast.error("Couldn't add the endpoint", { description: errorText(e) }),
		onSuccess: (e) => {
			onOpenChange(false);
			onCreated(e.secret);
		},
	});
	return (
		<Dialog onOpenChange={onOpenChange} open={open}>
			<DialogContent
				footer={
					<>
						<Button onClick={() => onOpenChange(false)}>Cancel</Button>
						<Button
							disabled={!url || create.isPending}
							onClick={() => create.mutate()}
							variant="primary"
						>
							{create.isPending ? "Adding…" : "Add endpoint"}
						</Button>
					</>
				}
				title="Add webhook endpoint"
			>
				<div className="grid gap-4">
					<Field
						help="Must use HTTPS. Production environments don't accept private network addresses."
						htmlFor="wh-url"
						label="Endpoint URL"
					>
						<Input
							className="font-mono"
							id="wh-url"
							onChange={(e) => setUrl(e.target.value)}
							placeholder="https://example.com/hooks/securefabric"
							value={url}
						/>
					</Field>
					<Field htmlFor="wh-desc" label="Description (optional)">
						<Input
							id="wh-desc"
							onChange={(e) => setDescription(e.target.value)}
							placeholder="Production event consumer"
							value={description}
						/>
					</Field>
					<Field help="Leave all unchecked to get every event." label="Events">
						<EventPicker onChange={setTypes} value={types} />
					</Field>
				</div>
			</DialogContent>
		</Dialog>
	);
}

function EndpointSheet({
	endpoint: e,
	onChanged,
	onDeleted,
	onSecret,
}: {
	endpoint: WebhookEndpoint;
	onChanged: () => void;
	onDeleted: () => void;
	onSecret: (s: string) => void;
}) {
	const { client, env } = useEnv();
	const access = useAccess();
	const canManage = access.allows(MANAGE);
	const queryClient = useQueryClient();
	const path = { endpoint_id: e.id };
	const deliveries = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/webhook_endpoints/{endpoint_id}/deliveries", {
					params: { path, query: { limit: 50 } },
				})
			),
		queryKey: ["deliveries", env.id, e.id],
		refetchInterval: 5000,
	});
	const [types, setTypes] = useState<string[]>(e.event_types);
	const [enabled, setEnabled] = useState(e.enabled);
	const [since, setSince] = useState(() =>
		new Date(Date.now() - 3_600_000).toISOString().slice(0, 16)
	);
	const [open, setOpen] = useState<string | null>(null);
	const reloadDeliveries = () =>
		queryClient.invalidateQueries({ queryKey: ["deliveries", env.id, e.id] });
	const save = useMutation({
		mutationFn: () =>
			unwrap(
				client.PATCH("/v1/webhook_endpoints/{endpoint_id}", {
					body: { enabled, event_types: types },
					params: { path },
				})
			),
		onError: (err) =>
			toast.error("Couldn't save the endpoint", {
				description: errorText(err),
			}),
		onSuccess: () => {
			toast.success("Endpoint saved");
			onChanged();
		},
	});
	const ping = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/webhook_endpoints/{endpoint_id}/ping", {
					headers: idem(),
					params: { path },
				})
			),
		onError: (err) =>
			toast.error("Couldn't send the test ping", {
				description: errorText(err),
			}),
		onSuccess: () => {
			toast.success("Test ping queued");
			reloadDeliveries();
		},
	});
	const rotate = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/webhook_endpoints/{endpoint_id}/rotate_secret", {
					headers: idem(),
					params: { path },
				})
			),
		onError: (err) =>
			toast.error("Couldn't rotate the secret", {
				description: errorText(err),
			}),
		onSuccess: (r) => {
			toast.success("Secret rotated", {
				description: "The old secret stays valid for 24 hours.",
			});
			onSecret((r as { secret: string }).secret);
			onChanged();
		},
	});
	const replayRange = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/webhook_endpoints/{endpoint_id}/replay", {
					body: { since: new Date(since).toISOString() },
					headers: idem(),
					params: { path },
				})
			),
		onError: (err) =>
			toast.error("Couldn't replay events", { description: errorText(err) }),
		onSuccess: (r) => {
			toast.success("Replay queued", {
				description: `${plural(r.replayed, "delivery", "deliveries")} will be sent again.`,
			});
			reloadDeliveries();
		},
	});
	const replay = useMutation({
		mutationFn: (id: string) =>
			unwrap(
				client.POST("/v1/webhook_deliveries/{delivery_id}/replay", {
					headers: idem(),
					params: { path: { delivery_id: id } },
				})
			),
		onError: (err) =>
			toast.error("Couldn't redeliver the event", {
				description: errorText(err),
			}),
		onSuccess: () => {
			toast.success("Redelivery queued");
			reloadDeliveries();
		},
	});
	const remove = useMutation({
		mutationFn: () =>
			unwrap(
				client.DELETE("/v1/webhook_endpoints/{endpoint_id}", {
					params: { path },
				})
			),
		onError: (err) =>
			toast.error("Couldn't delete the endpoint", {
				description: errorText(err),
			}),
		onSuccess: () => {
			toast.success("Endpoint deleted");
			onDeleted();
		},
	});
	const pingButton = (
		<Gated requires={MANAGE}>
			<Button
				disabled={ping.isPending}
				onClick={() => ping.mutate()}
				size="sm"
				variant="outline"
			>
				{ping.isPending ? "Sending…" : "Send test ping"}
			</Button>
		</Gated>
	);
	return (
		<SheetContent
			actions={
				<>
					{pingButton}
					<Gated requires={MANAGE}>
						<Button
							disabled={rotate.isPending}
							onClick={() => rotate.mutate()}
							size="sm"
							variant="outline"
						>
							{rotate.isPending ? "Rotating…" : "Rotate secret"}
						</Button>
					</Gated>
				</>
			}
			description={<span className="font-mono text-xs">{e.id}</span>}
			title={<span className="font-mono text-sm">{e.url}</span>}
		>
			<div className="grid gap-8 p-6">
				{e.previous_secret_expires_at ? (
					<p className="text-muted-foreground text-xs">
						The old secret stays valid until{" "}
						<When value={e.previous_secret_expires_at} />.
					</p>
				) : null}
				<Section title="Settings">
					<div className="flex items-center justify-between">
						<span className="text-sm">Send events to this endpoint</span>
						<Gated requires={MANAGE}>
							<Switch
								ariaLabel="Send events to this endpoint"
								checked={enabled}
								onChange={setEnabled}
							/>
						</Gated>
					</div>
					<Field help="Leave all unchecked to get every event." label="Events">
						<EventPicker
							disabled={!canManage}
							onChange={setTypes}
							value={types}
						/>
					</Field>
					<div className="flex gap-2">
						<Gated requires={MANAGE}>
							<Button
								disabled={save.isPending}
								onClick={() => save.mutate()}
								size="sm"
								variant="primary"
							>
								{save.isPending ? "Saving…" : "Save changes"}
							</Button>
						</Gated>
						<Gated requires={MANAGE}>
							<ConfirmButton
								confirmLabel="Delete endpoint"
								description="Events stop going to this endpoint and pending deliveries are dropped. You can't undo this."
								disabled={remove.isPending}
								onConfirm={() => remove.mutate()}
								title={`Delete the endpoint for ${hostOf(e.url)}?`}
							>
								{remove.isPending ? "Deleting…" : "Delete endpoint"}
							</ConfirmButton>
						</Gated>
					</div>
				</Section>
				<Section
					description="Resend every event since the time you choose."
					title="Replay events"
				>
					<div className="flex gap-2">
						<Input
							aria-label="Replay events since"
							className="h-8 w-56 text-sm"
							onChange={(ev) => setSince(ev.target.value)}
							type="datetime-local"
							value={since}
						/>
						<Gated requires={MANAGE}>
							<Button
								disabled={replayRange.isPending}
								onClick={() => replayRange.mutate()}
								size="sm"
								variant="outline"
							>
								{replayRange.isPending ? "Replaying…" : "Replay events"}
							</Button>
						</Gated>
					</div>
				</Section>
				<Section title="Recent deliveries">
					<QueryState
						empty={{
							action: pingButton,
							description:
								"Events sent to this endpoint appear here. Send a test ping to check it works.",
							title: "No deliveries yet",
							when: (deliveries.data ?? []).length === 0,
						}}
						query={deliveries}
						rows={3}
					>
						<Card>
							<Table>
								<thead>
									<Tr>
										<Th>Event</Th>
										<Th>Status</Th>
										<Th>Attempts</Th>
										<Th>Response</Th>
										<Th>Created</Th>
										<Th />
									</Tr>
								</thead>
								<tbody>
									{deliveries.data?.map((d) => (
										<Fragment key={d.id}>
											<Tr
												className="hover:bg-muted/40 cursor-pointer"
												onClick={() => setOpen(open === d.id ? null : d.id)}
											>
												<Td>
													<div className="text-sm">
														{eventLabel(d.event_type)}
													</div>
													<div className="text-muted-foreground font-mono text-xs">
														{d.event_type}
													</div>
												</Td>
												<Td>
													<Badge tone={DELIVERY_TONES[d.status] ?? "neutral"}>
														{DELIVERY_LABELS[d.status] ?? d.status}
													</Badge>
												</Td>
												<Td className="tabular-nums">{d.attempts}</Td>
												<Td className="text-xs whitespace-nowrap">
													{d.last_status_code ?? "—"}
													{d.last_latency_ms === null
														? ""
														: ` · ${d.last_latency_ms} ms`}
												</Td>
												<Td>
													<When value={d.created_at} />
												</Td>
												<Td className="text-right">
													<Gated requires={MANAGE}>
														<Button
															disabled={
																replay.isPending && replay.variables === d.id
															}
															onClick={(ev) => {
																ev.stopPropagation();
																replay.mutate(d.id);
															}}
															size="xs"
															variant="ghost"
														>
															Redeliver
														</Button>
													</Gated>
												</Td>
											</Tr>
											{open === d.id ? (
												<Tr>
													<Td colSpan={6}>
														{d.last_error ? (
															<p className="text-destructive mb-2 text-xs">
																{d.last_error}
															</p>
														) : null}
														<JsonBlock value={d.attempts_log} />
													</Td>
												</Tr>
											) : null}
										</Fragment>
									))}
								</tbody>
							</Table>
						</Card>
					</QueryState>
				</Section>
			</div>
		</SheetContent>
	);
}
