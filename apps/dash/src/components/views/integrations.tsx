"use client";

import { unwrap } from "@securefabric/client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { PageBody, PageHeader } from "@/components/common";
import {
	ConnectorLogo,
	errorText,
	QueryState,
	Section,
	When,
} from "@/components/kit";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, Select, Switch } from "@/components/ui/overlay";
import {
	Badge,
	Card,
	Field,
	Input,
	Table,
	Td,
	Textarea,
	Th,
	Tr,
} from "@/components/ui/primitives";
import type { Integration } from "@/lib/types";

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
	return (
		<>
			<PageHeader
				actions={
					<Button render={<Link href={href("/catalog")} />} variant="primary">
						Enable a connector
					</Button>
				}
				description="Connectors enabled in this environment: which streams run, how often, and which vendor app they use."
				title="Integrations"
			/>
			<PageBody className="grid gap-8">
				<QueryState
					empty={{
						description:
							"Enable one from the catalog. Creating a connection with only a vendor name also enables it.",
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
													<Badge tone="warn">deprecated</Badge>
												) : null}
											</Link>
										</Td>
										<Td>{i.enabled_streams.length}</Td>
										<Td className="text-muted-foreground">
											{i.vendor_app_id ? "Customer-owned" : "Platform default"}
										</Td>
										<Td>
											<Badge tone={i.write_back_enabled ? "accent" : "neutral"}>
												{i.write_back_enabled ? "on" : "off"}
											</Badge>
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
			toast.success("Vendor app registered", {
				description: "Secrets were sealed to this environment's key.",
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
				<Button onClick={() => setOpen(true)} size="sm" variant="outline">
					Register a GitHub App
				</Button>
			}
			description="App registrations connections authenticate through. Platform apps are shared; register your own for GitHub Enterprise Server or GHE.com."
			title="Vendor apps"
		>
			<QueryState query={apps}>
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
									<Td>{a.connector_id}</Td>
									<Td className="font-mono text-xs">{a.base_url}</Td>
									<Td>
										<Badge tone={a.owner === "platform" ? "neutral" : "accent"}>
											{a.owner}
										</Badge>
									</Td>
									<Td className="text-muted-foreground text-xs">
										{a.secrets_set ? "set" : "missing"} · webhook{" "}
										{a.webhook_secret_set ? "set" : "missing"}
									</Td>
								</Tr>
							))}
						</tbody>
					</Table>
				</Card>
			</QueryState>
			<Dialog onOpenChange={setOpen} open={open}>
				<DialogContent
					description="Secrets are write-only: sealed before the request returns and never shown again."
					footer={
						<>
							<Button onClick={() => setOpen(false)}>Cancel</Button>
							<Button
								disabled={create.isPending}
								onClick={() => create.mutate()}
								variant="primary"
							>
								Register
							</Button>
						</>
					}
					title="Register a GitHub App"
				>
					<div className="grid gap-3">
						<Field htmlFor="va-name" label="Name">
							<Input id="va-name" onChange={set("name")} value={form.name} />
						</Field>
						<Field
							help="https://github.example.com (GHES) or https://acme.ghe.com"
							htmlFor="va-base"
							label="Base URL"
						>
							<Input
								id="va-base"
								onChange={set("base_url")}
								value={form.base_url}
							/>
						</Field>
						<Field
							help="GHES: https://host/api/v3 · GHE.com: https://api.acme.ghe.com"
							htmlFor="va-api"
							label="API base URL"
						>
							<Input
								id="va-api"
								onChange={set("api_base_url")}
								value={form.api_base_url}
							/>
						</Field>
						<div className="grid grid-cols-2 gap-3">
							<Field htmlFor="va-appid" label="App ID">
								<Input
									id="va-appid"
									onChange={set("app_id")}
									value={form.app_id}
								/>
							</Field>
							<Field htmlFor="va-slug" label="Slug">
								<Input id="va-slug" onChange={set("slug")} value={form.slug} />
							</Field>
						</div>
						<Field htmlFor="va-client" label="Client ID">
							<Input
								id="va-client"
								onChange={set("client_id")}
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
								className="font-mono text-xs"
								id="va-pk"
								onChange={set("private_key")}
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
		onError: (e) => toast.error("Couldn't save", { description: errorText(e) }),
		onSuccess: async () => {
			await queryClient.invalidateQueries({
				queryKey: ["integrations", env.id],
			});
			toast.success("Saved");
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
			toast.error("Couldn't delete", { description: errorText(e) }),
		onSuccess: () => router.push(href("/integrations")),
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
							<Button onClick={() => remove.mutate()} variant="outline">
								Delete integration
							</Button>
						}
						description={`${i.connector_id} ${i.connector_version} · key ${i.key}`}
						title={
							<span className="flex items-center gap-3">
								<ConnectorLogo id={i.connector_id} size={32} />
								{i.display_name}
							</span>
						}
					/>
					<PageBody className="grid gap-8">
						<Section
							description="Streams that run for every connection of this integration, and their default interval"
							title="Streams"
						>
							<Card>
								<Table>
									<thead>
										<Tr>
											<Th>Stream</Th>
											<Th>Enabled</Th>
											<Th>Interval (minutes)</Th>
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
														<Switch
															ariaLabel={`Enable ${s.name}`}
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
													</Td>
													<Td>
														<Input
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
									help="Which app registration connections authenticate through"
									label="Vendor app"
								>
									<Select
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
								</Field>
								<div className="flex items-center justify-between gap-4">
									<div className="grid gap-0.5">
										<span className="text-sm font-medium">Write-back</span>
										<span className="text-muted-foreground text-xs">
											Lets POST
											/v1/vulnerability_findings/&#123;id&#125;/actions change
											state at the vendor. GitHub uses the read-and-write app.
										</span>
									</div>
									<Switch
										ariaLabel="Write-back"
										checked={i.write_back_enabled}
										onChange={(v) => update.mutate({ write_back_enabled: v })}
									/>
								</div>
							</Card>
						</Section>
					</PageBody>
				</>
			) : null}
		</QueryState>
	);
}
