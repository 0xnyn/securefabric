"use client";

import { unwrap } from "@securefabric/client";
import { Badge } from "@securefabric/ui/components/badge";
import { Button } from "@securefabric/ui/components/button";
import { Card } from "@securefabric/ui/components/card";
import { Dialog, DialogContent } from "@securefabric/ui/components/dialog";
import { Field, Input, Textarea } from "@securefabric/ui/components/form";
import { Select } from "@securefabric/ui/components/select";
import { Switch } from "@securefabric/ui/components/switch";
import { Table, Td, Th, Tr } from "@securefabric/ui/components/table";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { Section } from "@securefabric/ui/patterns/section";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlusIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Gated } from "@/components/domain/access";
import { ConnectorLogo } from "@/components/domain/connector-logo";
import { errorText, QueryState } from "@/components/domain/query-state";
import { When } from "@/components/domain/when";
import { useAccess, useEnv, useHref } from "@/components/shell/env-context";
import type { Integration } from "@/lib/types";
import { useConnectorInfo } from "./connections";
import { HeaderConfirmButton } from "./organizations";

export function useIntegrations() {
	const { client, env } = useEnv();
	return useQuery({
		queryFn: () => unwrap(client.GET("/v1/integrations")),
		queryKey: ["integrations", env.id],
	});
}

export function IntegrationsView() {
	const integrations = useIntegrations();
	const href = useHref();
	// Enabling happens on the catalog page; without provisioning:write it's
	// still worth browsing, so the link stays and only its wording changes.
	const canEnable = useAccess().can("provisioning:write");
	const catalogLabel = canEnable ? "Enable a connector" : "Browse catalog";
	return (
		<>
			<PageHeader
				actions={
					<Button render={<Link href={href("/catalog")} />} variant="primary">
						{catalogLabel}
					</Button>
				}
				description="Choose which streams run for each connector, and how often."
				title="Integrations"
			/>
			<PageBody className="grid gap-8">
				<QueryState
					empty={{
						action: (
							<Button
								render={<Link href={href("/catalog")} />}
								size="sm"
								variant="primary"
							>
								{catalogLabel}
							</Button>
						),
						description:
							"Enable a connector from the catalog. Adding a connection also enables its connector.",
						title: "No integrations yet",
						when: (integrations.data ?? []).length === 0,
					}}
					query={integrations}
				>
					<Card>
						<Table>
							<thead>
								<Tr>
									<Th>Integration</Th>
									<Th>Streams</Th>
									<Th>Vendor app</Th>
									<Th>Write-back</Th>
									<Th>Created</Th>
								</Tr>
							</thead>
							<tbody>
								{integrations.data?.map((i) => (
									<Tr className="hover:bg-muted/40" key={i.id}>
										<Td>
											<Link
												className="flex items-center gap-3"
												href={href(`/integrations/${i.id}`)}
											>
												<ConnectorLogo id={i.connector_id} />
												<span className="grid">
													<span className="font-medium">{i.display_name}</span>
													<span className="text-muted-foreground font-mono text-xs">
														{i.key}
													</span>
												</span>
												{i.deprecated ? (
													<Badge tone="warn">Deprecated</Badge>
												) : null}
											</Link>
										</Td>
										<Td className="tabular-nums">{i.enabled_streams.length}</Td>
										<Td className="text-muted-foreground">
											{i.vendor_app_id ? "Your own app" : "Platform default"}
										</Td>
										<Td className="text-muted-foreground">
											{i.write_back_enabled ? "On" : "Off"}
										</Td>
										<Td>
											<When value={i.created_at} />
										</Td>
									</Tr>
								))}
							</tbody>
						</Table>
					</Card>
				</QueryState>
				<VendorApps />
			</PageBody>
		</>
	);
}

function VendorApps() {
	const { client, env } = useEnv();
	const queryClient = useQueryClient();
	const apps = useQuery({
		queryFn: () => unwrap(client.GET("/v1/vendor_apps")),
		queryKey: ["vendor_apps", env.id],
	});
	const connector = useConnectorInfo();
	const [open, setOpen] = useState(false);
	const [form, setForm] = useState({
		api_base_url: "",
		app_id: "",
		base_url: "",
		client_id: "",
		client_secret: "",
		name: "",
		private_key: "",
		slug: "",
		webhook_secret: "",
	});
	const create = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/vendor_apps", {
					body: {
						base_url: form.base_url,
						config: {
							api_base_url: form.api_base_url || undefined,
							app_id: form.app_id,
							client_id: form.client_id,
							permission_tier: "read",
							slug: form.slug,
						},
						connector_id: "GITHUB",
						name: form.name,
						secrets: {
							client_secret: form.client_secret,
							private_key: form.private_key,
						},
						webhook_secret: form.webhook_secret || null,
					},
				})
			),
		onError: (e) =>
			toast.error("Couldn't register the app", { description: errorText(e) }),
		onSuccess: async () => {
			await queryClient.invalidateQueries({
				queryKey: ["vendor_apps", env.id],
			});
			setOpen(false);
			toast.success("GitHub App registered", {
				description: "Its secrets are encrypted with this environment's key.",
			});
		},
	});
	const set =
		(k: keyof typeof form) =>
		(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
			setForm({ ...form, [k]: e.target.value });
	return (
		<Section
			action={
				<Gated requires={{ scope: "provisioning:write" }}>
					<Button onClick={() => setOpen(true)} size="sm" variant="outline">
						<PlusIcon /> Register GitHub App
					</Button>
				</Gated>
			}
			description="The apps connections sign in through. Register your own for GitHub Enterprise Server or GHE.com."
			title="Vendor apps"
		>
			<QueryState
				empty={{
					action: (
						<Gated requires={{ scope: "provisioning:write" }}>
							<Button onClick={() => setOpen(true)} size="sm" variant="primary">
								<PlusIcon /> Register GitHub App
							</Button>
						</Gated>
					),
					description:
						"Connections use the shared default apps. Register your own to connect GitHub Enterprise Server or GHE.com.",
					title: "No vendor apps yet",
					when: (apps.data ?? []).length === 0,
				}}
				query={apps}
			>
				<Card>
					<Table>
						<thead>
							<Tr>
								<Th>Name</Th>
								<Th>Connector</Th>
								<Th>Base URL</Th>
								<Th>Owner</Th>
								<Th>Secrets</Th>
							</Tr>
						</thead>
						<tbody>
							{apps.data?.map((a) => (
								<Tr key={a.id}>
									<Td className="font-medium">{a.name}</Td>
									<Td>
										<span className="inline-flex items-center gap-2">
											<ConnectorLogo
												id={a.connector_id}
												logo={connector(a.connector_id).logo}
												name={connector(a.connector_id).name}
												size={20}
											/>
											{connector(a.connector_id).name}
										</span>
									</Td>
									<Td className="font-mono text-xs">{a.base_url}</Td>
									<Td className="text-muted-foreground">
										{a.owner === "platform" ? "Platform" : "Yours"}
									</Td>
									<Td className="text-muted-foreground text-sm">
										{a.secrets_set
											? "App secrets saved"
											: "App secrets missing"}
										{" · "}
										{a.webhook_secret_set
											? "webhook secret saved"
											: "no webhook secret"}
									</Td>
								</Tr>
							))}
						</tbody>
					</Table>
				</Card>
			</QueryState>
			<Dialog onOpenChange={setOpen} open={open}>
				<DialogContent
					description="For GitHub Enterprise Server or GHE.com. Secrets are encrypted when you save and never shown again."
					footer={
						<>
							<Button onClick={() => setOpen(false)}>Cancel</Button>
							<Gated requires={{ scope: "provisioning:write" }}>
								<Button
									disabled={create.isPending}
									onClick={() => create.mutate()}
									variant="primary"
								>
									{create.isPending ? "Registering…" : "Register app"}
								</Button>
							</Gated>
						</>
					}
					title="Register GitHub App"
				>
					<div className="grid gap-3">
						<Field htmlFor="va-name" label="Name">
							<Input
								id="va-name"
								onChange={set("name")}
								placeholder="Acme GitHub Enterprise"
								value={form.name}
							/>
						</Field>
						<Field
							help="Your GitHub Enterprise Server or GHE.com address."
							htmlFor="va-base"
							label="Base URL"
						>
							<Input
								id="va-base"
								onChange={set("base_url")}
								placeholder="https://github.example.com"
								value={form.base_url}
							/>
						</Field>
						<Field
							help="For GHE.com, use https://api.<name>.ghe.com."
							htmlFor="va-api"
							label="API base URL"
						>
							<Input
								id="va-api"
								onChange={set("api_base_url")}
								placeholder="https://github.example.com/api/v3"
								value={form.api_base_url}
							/>
						</Field>
						<div className="grid grid-cols-2 gap-3">
							<Field htmlFor="va-appid" label="App ID">
								<Input
									id="va-appid"
									onChange={set("app_id")}
									placeholder="123456"
									value={form.app_id}
								/>
							</Field>
							<Field htmlFor="va-slug" label="Slug">
								<Input
									id="va-slug"
									onChange={set("slug")}
									placeholder="acme-security"
									value={form.slug}
								/>
							</Field>
						</div>
						<Field htmlFor="va-client" label="Client ID">
							<Input
								id="va-client"
								onChange={set("client_id")}
								placeholder="Iv23liExample"
								value={form.client_id}
							/>
						</Field>
						<Field htmlFor="va-cs" label="Client secret">
							<Input
								id="va-cs"
								onChange={set("client_secret")}
								type="password"
								value={form.client_secret}
							/>
						</Field>
						<Field htmlFor="va-pk" label="Private key (PEM)">
							<Textarea
								className="font-mono"
								id="va-pk"
								onChange={set("private_key")}
								placeholder="Paste the whole .pem file, including the BEGIN and END lines"
								rows={4}
								value={form.private_key}
							/>
						</Field>
						<Field htmlFor="va-wh" label="Webhook secret">
							<Input
								id="va-wh"
								onChange={set("webhook_secret")}
								type="password"
								value={form.webhook_secret}
							/>
						</Field>
					</div>
				</DialogContent>
			</Dialog>
		</Section>
	);
}

/** The success toast for an integration update, named for what changed. */
function updatedMessage(body: Partial<Integration>): string {
	if (body.write_back_enabled !== undefined) {
		return body.write_back_enabled
			? "Write-back turned on"
			: "Write-back turned off";
	}
	if (body.enabled_streams) {
		return "Streams updated";
	}
	if (body.stream_intervals) {
		return "Interval updated";
	}
	if (body.vendor_app_id !== undefined) {
		return "Vendor app changed";
	}
	return "Integration updated";
}

export function IntegrationView({ id }: { id: string }) {
	const { client, env } = useEnv();
	const href = useHref();
	const router = useRouter();
	const queryClient = useQueryClient();
	const integration = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/integrations/{integration_id}", {
					params: { path: { integration_id: id } },
				})
			),
		queryKey: ["integrations", env.id, id],
	});
	const connector = useQuery({
		enabled: Boolean(integration.data),
		queryFn: () =>
			unwrap(
				client.GET("/v1/connectors/{connector_id}", {
					params: {
						path: { connector_id: integration.data?.connector_id ?? "" },
					},
				})
			),
		queryKey: ["connectors", integration.data?.connector_id],
	});
	const apps = useQuery({
		queryFn: () => unwrap(client.GET("/v1/vendor_apps")),
		queryKey: ["vendor_apps", env.id],
	});
	const update = useMutation({
		mutationFn: (body: Partial<Integration>) =>
			unwrap(
				client.PATCH("/v1/integrations/{integration_id}", {
					body: body as never,
					params: { path: { integration_id: id } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't update the integration", {
				description: errorText(e),
			}),
		onSuccess: async (_, body) => {
			await queryClient.invalidateQueries({
				queryKey: ["integrations", env.id],
			});
			toast.success(updatedMessage(body));
		},
	});
	const remove = useMutation({
		mutationFn: () =>
			unwrap(
				client.DELETE("/v1/integrations/{integration_id}", {
					params: { path: { integration_id: id } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't delete the integration", {
				description: errorText(e),
			}),
		onSuccess: () => {
			toast.success("Integration deleted");
			router.push(href("/integrations"));
		},
	});
	const i = integration.data;
	const streams = (connector.data?.streams ?? []) as {
		name: string;
		title: string;
		interval: { default: number; min: number; max: number };
	}[];
	return (
		<QueryState query={integration}>
			{i ? (
				<>
					<PageHeader
						actions={
							<Gated requires={{ scope: "provisioning:write" }}>
								<HeaderConfirmButton
									confirmLabel="Delete integration"
									description="Delete its connections first. You can't undo this."
									disabled={remove.isPending}
									onConfirm={() => remove.mutate()}
									title={`Delete “${i.display_name}”?`}
								>
									{remove.isPending ? "Deleting…" : "Delete integration"}
								</HeaderConfirmButton>
							</Gated>
						}
						description={
							<span>
								{connector.data?.name ?? i.connector_id} {i.connector_version}
								{" · Key "}
								<span className="font-mono">{i.key}</span>
							</span>
						}
						title={
							<span className="flex items-center gap-3">
								<ConnectorLogo
									id={i.connector_id}
									logo={connector.data?.logo_url}
									name={connector.data?.name ?? i.display_name}
									size={32}
								/>
								{i.display_name}
							</span>
						}
					/>
					<PageBody className="grid gap-8">
						<Section
							description="Which streams run for this integration's connections, and how often."
							title="Streams"
						>
							<Card>
								<Table>
									<thead>
										<Tr>
											<Th>Stream</Th>
											<Th>On</Th>
											<Th>Runs every (minutes)</Th>
										</Tr>
									</thead>
									<tbody>
										{streams.map((s) => {
											const on = i.enabled_streams.includes(s.name);
											const current =
												i.stream_intervals[s.name] ?? s.interval.default;
											return (
												<Tr key={s.name}>
													<Td>
														<div className="font-medium">{s.title}</div>
														<div className="text-muted-foreground font-mono text-xs">
															{s.name}
														</div>
													</Td>
													<Td>
														<Gated requires={{ scope: "provisioning:write" }}>
															<Switch
																ariaLabel={`Run ${s.title}`}
																checked={on}
																onChange={(v) =>
																	update.mutate({
																		enabled_streams: v
																			? [...i.enabled_streams, s.name]
																			: i.enabled_streams.filter(
																					(x) => x !== s.name
																				),
																	})
																}
															/>
														</Gated>
													</Td>
													<Td>
														<Gated requires={{ scope: "provisioning:write" }}>
															<Input
																aria-label={`How often ${s.title} runs, in minutes`}
																className="w-28"
																defaultValue={current / 60}
																max={s.interval.max / 60}
																min={s.interval.min / 60}
																onBlur={(e) => {
																	const v = Math.round(
																		Number(e.target.value) * 60
																	);
																	if (v && v !== current) {
																		update.mutate({
																			stream_intervals: {
																				...i.stream_intervals,
																				[s.name]: v,
																			},
																		});
																	}
																}}
																type="number"
															/>
														</Gated>
													</Td>
												</Tr>
											);
										})}
									</tbody>
								</Table>
							</Card>
						</Section>
						<Section title="Vendor app and write-back">
							<Card className="grid gap-4 p-5">
								<Field
									help="The app this integration's connections sign in through."
									label="Vendor app"
								>
									<Gated requires={{ scope: "provisioning:write" }}>
										<Select
											ariaLabel="Vendor app"
											onChange={(v) =>
												update.mutate({
													vendor_app_id: v === "default" ? null : v,
												})
											}
											options={[
												{ label: "Platform default", value: "default" },
												...(apps.data ?? [])
													.filter(
														(a) =>
															a.owner !== "platform" &&
															a.connector_id === i.connector_id
													)
													.map((a) => ({ label: a.name, value: a.id })),
											]}
											value={i.vendor_app_id ?? "default"}
										/>
									</Gated>
								</Field>
								<div className="flex items-center justify-between gap-4">
									<div className="grid gap-0.5">
										<span className="text-sm font-medium">Write-back</span>
										<span className="text-muted-foreground text-xs">
											Lets write-back actions change a finding's state at the
											vendor, via{" "}
											<code className="font-mono">
												POST /v1/vulnerability_findings/&#123;id&#125;/actions
											</code>
											. GitHub uses the read-and-write app.
										</span>
									</div>
									<Gated requires={{ scope: "provisioning:write" }}>
										<Switch
											ariaLabel="Write-back"
											checked={i.write_back_enabled}
											onChange={(v) => update.mutate({ write_back_enabled: v })}
										/>
									</Gated>
								</div>
							</Card>
						</Section>
					</PageBody>
				</>
			) : null}
		</QueryState>
	);
}
