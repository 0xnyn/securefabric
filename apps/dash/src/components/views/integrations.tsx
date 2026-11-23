"use client";

import { ArrowLeftIcon, BoxesIcon, PlusIcon, Trash2Icon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import {
	CopyField,
	PageBody,
	PageHeader,
	ProviderLogo,
	Tabs,
} from "@/components/common";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button, buttonVariants } from "@/components/ui/button";
import { Select, Switch } from "@/components/ui/overlay";
import {
	Badge,
	Card,
	CardHeader,
	Dot,
	EmptyState,
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
import { timeAgo } from "@/lib/format";
import { INTEGRATION_TABS, type IntegrationTab } from "@/lib/nav";
import { deleteIntegration, updateIntegration } from "@/lib/store";
import { useZustandAdapter } from "@/lib/store/adapters/zustand";
import { DataTableStoreProvider } from "@/lib/store/provider/DataTableStoreProvider";
import {
	type Connection,
	FREQUENCY_LABELS,
	HEALTH,
	type Integration,
	type SyncFrequency,
} from "@/lib/types";
import { useSearchParam } from "@/lib/use-search-param";
import {
	ConnectionsTable,
	INTEGRATION_FIXED_FILTERS,
} from "./connections/connections-table";
import { filterSchema, useEmbeddedFilterStore } from "./connections/schema";

export function IntegrationsView() {
	const { env } = useEnv();
	const href = useHref();
	const router = useRouter();
	return (
		<>
			<PageHeader
				actions={
					<Link
						className={buttonVariants({ variant: "primary" })}
						href={href("/catalog")}
					>
						<PlusIcon />
						Enable integration
					</Link>
				}
				description={`Integrations enabled in ${env.name}. Each one sets which models sync, how often, and whether sandbox connections are allowed.`}
				title="Integrations"
			/>
			<PageBody>
				{env.integrations.length === 0 ? (
					<EmptyState
						action={
							<Link
								className={buttonVariants({ variant: "primary" })}
								href={href("/catalog")}
							>
								Browse catalog
							</Link>
						}
						description="Pick the tools your customers run from the catalog. You can enable as many as you like."
						icon={<BoxesIcon className="size-4" />}
						title="No integrations enabled"
					/>
				) : (
					<Card className="overflow-hidden">
						<Table>
							<thead>
								<tr>
									<Th>Integration</Th>
									<Th className="hidden md:table-cell">Models</Th>
									<Th>Connections</Th>
									<Th className="hidden lg:table-cell">Sync</Th>
									<Th className="hidden sm:table-cell">Sandbox</Th>
									<Th className="hidden xl:table-cell">Enabled</Th>
								</tr>
							</thead>
							<tbody>
								{env.integrations.map((i) => {
									const p = providerOrThrow(i.provider);
									const conns = env.connections.filter(
										(c) => c.integrationId === i.id
									);
									const failing = conns.filter(
										(c) => HEALTH[c.health].tone === "error"
									).length;
									return (
										<Tr
											className="cursor-pointer"
											key={i.id}
											onClick={() => router.push(href(`/integrations/${i.id}`))}
										>
											<Td>
												<Link
													className="flex items-center gap-3 py-2"
													href={href(`/integrations/${i.id}`)}
													onClick={(e) => e.stopPropagation()}
												>
													<ProviderLogo provider={p} size={32} />
													<span className="grid">
														<span className="font-medium">{p.name}</span>
														<span className="text-2xs text-muted-foreground font-mono">
															{i.id}
														</span>
													</span>
												</Link>
											</Td>
											<Td className="hidden md:table-cell">
												<div className="flex flex-wrap gap-1">
													{i.models.map((m) => (
														<span
															className="border-border text-2xs text-muted-foreground rounded border px-1.5 py-0.5 font-mono"
															key={m}
														>
															{MODELS[m].name}
														</span>
													))}
												</div>
											</Td>
											<Td>
												<span className="inline-flex items-center gap-2 tabular-nums">
													{conns.length}
													{failing ? (
														<Badge tone="error">
															<Dot className="size-1.5" tone="error" />
															{failing} failing
														</Badge>
													) : null}
												</span>
											</Td>
											<Td className="text-muted-foreground hidden lg:table-cell">
												{FREQUENCY_LABELS[i.syncFrequency]}
											</Td>
											<Td className="hidden sm:table-cell">
												{i.allowSandbox ? (
													<Badge tone="accent">Allowed</Badge>
												) : (
													<span className="text-muted-foreground">Off</span>
												)}
											</Td>
											<Td className="text-muted-foreground hidden xl:table-cell">
												{timeAgo(i.createdAt)}
											</Td>
										</Tr>
									);
								})}
							</tbody>
						</Table>
					</Card>
				)}
			</PageBody>
		</>
	);
}

type Tab = IntegrationTab;

const TAB_VALUES = INTEGRATION_TABS.map((t) => t.value);

export function IntegrationView({ id }: { id: string }) {
	const { env } = useEnv();
	const href = useHref();
	const integration = env.integrations.find((i) => i.id === id);
	if (!integration) {
		return (
			<PageBody>
				<EmptyState
					action={
						<Link className={buttonVariants()} href={href("/integrations")}>
							Back to integrations
						</Link>
					}
					description={`No integration "${id}" is enabled in ${env.name}.`}
					title="Integration not found"
				/>
			</PageBody>
		);
	}
	return <IntegrationDetail integration={integration} />;
}

function IntegrationDetail({ integration }: { integration: Integration }) {
	const { env } = useEnv();
	const href = useHref();
	const [tab, setTab] = useSearchParam<Tab>("tab", TAB_VALUES, "connections");
	const p = providerOrThrow(integration.provider);
	const conns = env.connections.filter(
		(c) => c.integrationId === integration.id
	);
	return (
		<>
			<div className="border-border bg-background border-b">
				<div className="px-4 pt-6 sm:px-8">
					<Link
						className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-sm"
						href={href("/integrations")}
					>
						<ArrowLeftIcon className="size-3.5" />
						Integrations
					</Link>
					<div className="flex flex-col gap-4 py-6 sm:flex-row sm:items-center sm:justify-between">
						<div className="flex items-center gap-4">
							<ProviderLogo provider={p} size={48} />
							<div className="grid gap-1">
								<h1 className="tracking-heading text-2xl font-semibold">
									{p.name}
								</h1>
								<p className="text-muted-foreground text-sm">
									<span className="font-mono">{integration.id}</span> ·{" "}
									{AUTH_LABELS[p.auth]} ·{" "}
									{FREQUENCY_LABELS[integration.syncFrequency]}
								</p>
							</div>
						</div>
						<div className="flex gap-2">
							<Link
								className={buttonVariants()}
								href={href(`/catalog/${p.slug}`)}
							>
								Catalog page
							</Link>
							<Link
								className={buttonVariants({ variant: "primary" })}
								href={href(`/connections?new=1&integration=${integration.id}`)}
							>
								<PlusIcon />
								Add connection
							</Link>
						</div>
					</div>
					<div>
						<Tabs
							onChange={setTab}
							tabs={[
								{
									count: conns.length,
									label: "Connections",
									value: "connections",
								},
								{ label: "Configuration", value: "configuration" },
								{ label: "Settings", value: "settings" },
							]}
							value={tab}
						/>
					</div>
				</div>
			</div>
			<PageBody>
				{tab === "connections" ? (
					<ConnectionsTab integration={integration} />
				) : null}
				{tab === "configuration" ? (
					<ConfigurationTab integration={integration} />
				) : null}
				{tab === "settings" ? <SettingsTab integration={integration} /> : null}
			</PageBody>
		</>
	);
}

function ConnectionsTab({ integration }: { integration: Integration }) {
	const { env } = useEnv();
	const href = useHref();
	const conns = env.connections.filter(
		(c) => c.integrationId === integration.id
	);
	if (conns.length === 0) {
		return (
			<EmptyState
				action={
					<Link
						className={buttonVariants({ variant: "primary" })}
						href={href(`/connections?new=1&integration=${integration.id}`)}
					>
						Add connection
					</Link>
				}
				description={
					integration.allowSandbox
						? "Start with a sandbox connection: no credentials, realistic data."
						: "Send a customer a Connect link to create the first one."
				}
				title="No connections yet"
			/>
		);
	}
	return (
		<EmbeddedConnections connections={conns} integrationId={integration.id} />
	);
}

/** The same table as the connections page, with its filters in memory
 * (zustand) instead of the URL, which already names the tab. */
function EmbeddedConnections({
	connections,
	integrationId,
}: {
	connections: Connection[];
	integrationId: string;
}) {
	const adapter = useZustandAdapter(
		useEmbeddedFilterStore,
		filterSchema.definition,
		{ id: "integration-connections" }
	);
	return (
		<DataTableStoreProvider adapter={adapter}>
			<ConnectionsTable
				connections={connections}
				omitFilters={INTEGRATION_FIXED_FILTERS}
				tableId={`integration-connections:${integrationId}`}
			/>
		</DataTableStoreProvider>
	);
}

function ConfigurationTab({ integration }: { integration: Integration }) {
	const { env } = useEnv();
	const p = providerOrThrow(integration.provider);
	const toggleModel = (m: ModelKey): void => {
		const models = integration.models.includes(m)
			? integration.models.filter((x) => x !== m)
			: [...integration.models, m];
		updateIntegration(env.slug, integration.id, { models });
		toast.success("Models updated", {
			description: "Applies from each connection's next sync.",
		});
	};
	const toggleScope = (scope: string): void => {
		const writeScopes = integration.writeScopes.includes(scope)
			? integration.writeScopes.filter((x) => x !== scope)
			: [...integration.writeScopes, scope];
		updateIntegration(env.slug, integration.id, { writeScopes });
	};
	return (
		<div className="grid max-w-3xl gap-6">
			<Card>
				<CardHeader
					description="Customers see these scopes in SecureFabric Connect before they connect."
					title="Models"
				/>
				<ul className="divide-border divide-y">
					{p.models.map((m) => (
						<li
							className="flex items-center justify-between gap-4 px-5 py-4"
							key={m}
						>
							<div className="grid gap-0.5">
								<span className="flex items-center gap-2 text-sm">
									<span className="font-mono">{MODELS[m].name}</span>
									<span className="text-2xs text-muted-foreground font-mono">
										{MODELS[m].scope}
									</span>
								</span>
								<span className="text-muted-foreground text-xs">
									{MODELS[m].description}
								</span>
							</div>
							<Switch
								ariaLabel={`Sync ${MODELS[m].name}`}
								checked={integration.models.includes(m)}
								onChange={() => toggleModel(m)}
							/>
						</li>
					))}
				</ul>
			</Card>
			{p.writeActions.length > 0 ? (
				<Card>
					<CardHeader
						description="Off by default. Connections stay read-only until a customer approves a write scope."
						title="Write actions"
					/>
					<ul className="divide-border divide-y">
						{p.writeActions.map((a) => (
							<li
								className="flex items-center justify-between gap-4 px-5 py-4"
								key={a.scope}
							>
								<div className="grid gap-0.5">
									<span className="text-sm">{a.name}</span>
									<span className="text-2xs text-muted-foreground font-mono">
										{a.endpoint} · {a.scope}
									</span>
								</div>
								<Switch
									ariaLabel={a.name}
									checked={integration.writeScopes.includes(a.scope)}
									onChange={() => toggleScope(a.scope)}
								/>
							</li>
						))}
					</ul>
				</Card>
			) : null}
			<Card>
				<CardHeader
					description="Incremental syncs fetch only what changed. Connections can override this."
					title="Sync frequency"
				/>
				<div className="px-5 py-4 sm:w-80">
					<Select
						ariaLabel="Sync frequency"
						onChange={(v) => {
							updateIntegration(env.slug, integration.id, { syncFrequency: v });
							toast.success("Sync frequency updated");
						}}
						options={(Object.keys(FREQUENCY_LABELS) as SyncFrequency[]).map(
							(f) => ({ label: FREQUENCY_LABELS[f], value: f })
						)}
						value={integration.syncFrequency}
					/>
				</div>
			</Card>
			<Card>
				<div className="flex items-start justify-between gap-4 px-5 py-4">
					<div className="grid gap-1">
						<p className="text-sm font-medium">Allow sandbox connections</p>
						<p className="text-muted-foreground text-sm">
							Lets you and your customers connect without vendor credentials and
							read generated data.
						</p>
					</div>
					<Switch
						ariaLabel="Allow sandbox connections"
						checked={integration.allowSandbox}
						onChange={(v) =>
							updateIntegration(env.slug, integration.id, { allowSandbox: v })
						}
					/>
				</div>
			</Card>
		</div>
	);
}

const KEY_CHARS = /[^a-z0-9-]/gu;

function SettingsTab({ integration }: { integration: Integration }) {
	const { env } = useEnv();
	const href = useHref();
	const router = useRouter();
	const [key, setKey] = useState(integration.id);
	const count = env.connections.filter(
		(c) => c.integrationId === integration.id
	).length;
	return (
		<div className="grid max-w-3xl gap-6">
			<Card>
				<CardHeader
					description="Used as integrationId in connect sessions and the API. Renaming breaks code that hard-codes the old ID."
					title="Integration ID"
				/>
				<form
					className="flex flex-col gap-2 px-5 py-4 sm:flex-row"
					onSubmit={(e) => {
						e.preventDefault();
						if (!key || key === integration.id) {
							return;
						}
						if (env.integrations.some((i) => i.id === key)) {
							toast.error(`"${key}" is already used in ${env.name}`);
							return;
						}
						updateIntegration(env.slug, integration.id, { id: key });
						toast.success("Integration ID updated");
						router.replace(href(`/integrations/${key}`));
					}}
				>
					<Input
						aria-label="Integration ID"
						className="font-mono"
						onChange={(e) =>
							setKey(e.target.value.toLowerCase().replace(KEY_CHARS, ""))
						}
						value={key}
					/>
					<Button type="submit">Save</Button>
				</form>
			</Card>
			<Card>
				<CardHeader
					description="For OAuth integrations, register this redirect URI in the vendor's app settings."
					title="Callback URL"
				/>
				<div className="px-5 py-4">
					<CopyField label="Callback URL" value={env.callbackUrl} />
				</div>
			</Card>
			<Card className="border-destructive/30">
				<CardHeader
					description={`Deletes the integration and its ${count} connection${count === 1 ? "" : "s"} in ${env.name}. Stored credentials are destroyed.`}
					title="Delete integration"
				/>
				<div className="flex justify-end px-5 py-4">
					<Button
						onClick={() => {
							deleteIntegration(env.slug, integration.id);
							toast.success("Integration deleted");
							router.push(href("/integrations"));
						}}
						variant="destructive"
					>
						<Trash2Icon />
						Delete integration
					</Button>
				</div>
			</Card>
		</div>
	);
}
