"use client";

import { unwrap } from "@securefabric/client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { toast } from "sonner";
import { CopyField, PageBody, PageHeader } from "@/components/common";
import {
	ConfirmButton,
	errorText,
	JsonBlock,
	QueryState,
	Section,
	StatusBadge,
	When,
} from "@/components/kit";
import { useEnv } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	SheetContent,
	Switch,
} from "@/components/ui/overlay";
import {
	Badge,
	Card,
	Field,
	Input,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";
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

const idem = () => ({ "Idempotency-Key": crypto.randomUUID() });

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
	return (
		<>
			<PageHeader
				actions={
					<Button onClick={() => setCreating(true)} variant="primary">
						Add endpoint
					</Button>
				}
				description="Signed event deliveries (Standard Webhooks) with retries, replay and secret rotation."
				title="Webhooks"
			/>
			<PageBody>
				<QueryState
					empty={{
						action: (
							<Button
								onClick={() => setCreating(true)}
								size="sm"
								variant="primary"
							>
								Add endpoint
							</Button>
						),
						description:
							"Receive connection and sync events at an HTTPS URL you control.",
						title: "No endpoints",
						when: (endpoints.data ?? []).length === 0,
					}}
					query={endpoints}
				>
					<Card>
						<Table>
							<thead>
								<Tr>
									<Th>URL</Th>
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
										<Td className="text-xs">
											{e.event_types.length ? e.event_types.length : "all"}
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
					description="Shown once. Verify deliveries with it (webhook-signature header)."
					footer={
						<Button onClick={() => setSecret(null)} variant="primary">
							I've saved it
						</Button>
					}
					title="Signing secret"
				>
					{secret ? <CopyField label="Signing secret" value={secret} /> : null}
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

function EndpointStatus({ endpoint: e }: { endpoint: WebhookEndpoint }) {
	if (!e.enabled) {
		return (
			<Badge>
				disabled{e.disabled_reason ? ` · ${e.disabled_reason}` : ""}
			</Badge>
		);
	}
	return e.failing_since ? (
		<Badge tone="warn">failing</Badge>
	) : (
		<Badge tone="ok">enabled</Badge>
	);
}

function EventPicker({
	value,
	onChange,
}: {
	value: string[];
	onChange: (v: string[]) => void;
}) {
	return (
		<div className="grid gap-1.5 sm:grid-cols-2">
			{EVENT_TYPES.map((t) => (
				<label className="flex items-center gap-2 text-xs" key={t}>
					<input
						checked={value.includes(t)}
						onChange={(e) =>
							onChange(
								e.target.checked ? [...value, t] : value.filter((x) => x !== t)
							)
						}
						type="checkbox"
					/>
					<span className="font-mono">{t}</span>
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
					<Button
						disabled={!url || create.isPending}
						onClick={() => create.mutate()}
						variant="primary"
					>
						Add endpoint
					</Button>
				}
				title="Add webhook endpoint"
			>
				<div className="grid gap-4">
					<Field
						help="HTTPS; private addresses are refused in production"
						htmlFor="wh-url"
						label="URL"
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
							value={description}
						/>
					</Field>
					<Field help="None selected means every event" label="Events">
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
			toast.error("Couldn't save", { description: errorText(err) }),
		onSuccess: () => {
			toast.success("Saved");
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
			toast.error("Ping failed", { description: errorText(err) }),
		onSuccess: () => {
			toast.success("Ping queued");
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
			toast.error("Couldn't rotate", { description: errorText(err) }),
		onSuccess: (r) => {
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
			toast.error("Couldn't replay", { description: errorText(err) }),
		onSuccess: (r) => {
			toast.success("Replay queued", { description: JSON.stringify(r) });
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
			toast.error("Couldn't replay", { description: errorText(err) }),
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
			toast.error("Couldn't delete", { description: errorText(err) }),
		onSuccess: onDeleted,
	});
	return (
		<SheetContent
			actions={
				<>
					<Button
						disabled={ping.isPending}
						onClick={() => ping.mutate()}
						size="sm"
						variant="outline"
					>
						Send ping
					</Button>
					<Button
						disabled={rotate.isPending}
						onClick={() => rotate.mutate()}
						size="sm"
						variant="outline"
					>
						Rotate secret
					</Button>
				</>
			}
			description={<span className="font-mono text-xs">{e.id}</span>}
			title={<span className="font-mono text-sm">{e.url}</span>}
		>
			<div className="grid gap-8 p-6">
				{e.previous_secret_expires_at ? (
					<p className="text-muted-foreground text-xs">
						The previous secret keeps signing until{" "}
						<When value={e.previous_secret_expires_at} />.
					</p>
				) : null}
				<Section title="Settings">
					<div className="flex items-center justify-between">
						<span className="text-sm">Enabled</span>
						<Switch
							ariaLabel="Enabled"
							checked={enabled}
							onChange={setEnabled}
						/>
					</div>
					<EventPicker onChange={setTypes} value={types} />
					<div className="flex gap-2">
						<Button
							disabled={save.isPending}
							onClick={() => save.mutate()}
							size="sm"
							variant="primary"
						>
							Save
						</Button>
						<ConfirmButton
							confirmLabel="Delete endpoint"
							description="Pending deliveries to it are dropped."
							onConfirm={() => remove.mutate()}
							title="Delete this endpoint?"
						>
							Delete
						</ConfirmButton>
					</div>
				</Section>
				<Section
					description="Re-send every event since a point in time"
					title="Replay"
				>
					<div className="flex gap-2">
						<Input
							className="w-56"
							onChange={(ev) => setSince(ev.target.value)}
							type="datetime-local"
							value={since}
						/>
						<Button
							disabled={replayRange.isPending}
							onClick={() => replayRange.mutate()}
							size="sm"
							variant="outline"
						>
							Replay since
						</Button>
					</div>
				</Section>
				<Section title="Recent deliveries">
					<QueryState
						empty={{
							description: "Send a ping to test the endpoint.",
							title: "No deliveries",
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
												<Td className="font-mono text-xs">{d.event_type}</Td>
												<Td>
													<StatusBadge
														tones={DELIVERY_TONES}
														value={d.status}
													/>
												</Td>
												<Td className="tabular-nums">{d.attempts}</Td>
												<Td className="text-xs">
													{d.last_status_code ?? "—"}
													{d.last_latency_ms === null
														? ""
														: ` · ${d.last_latency_ms} ms`}
												</Td>
												<Td>
													<When value={d.created_at} />
												</Td>
												<Td>
													<Button
														onClick={(ev) => {
															ev.stopPropagation();
															replay.mutate(d.id);
														}}
														size="xs"
														variant="ghost"
													>
														Replay
													</Button>
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
