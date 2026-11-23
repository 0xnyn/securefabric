"use client";

import {
	ArrowLeftIcon,
	CheckIcon,
	ExternalLinkIcon,
	FlaskConicalIcon,
	KeyRoundIcon,
	LockIcon,
	PlusIcon,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import {
	CodeBlock,
	CodeTabs,
	PageBody,
	ProviderLogo,
	Tabs,
} from "@/components/common";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button, buttonVariants } from "@/components/ui/button";
import { Select } from "@/components/ui/overlay";
import {
	Badge,
	Card,
	CardHeader,
	EmptyState,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";
import { apiPath } from "@/lib/api-paths";
import {
	AUTH_LABELS,
	CATEGORIES,
	getProvider,
	MODELS,
	type ModelKey,
	type Provider,
	STATUS_LABELS,
} from "@/lib/catalog";
import { type ProviderTab, providerTabs } from "@/lib/nav";
import { generateRecords, SANDBOX_DOMAIN } from "@/lib/records";
import { samples, sdkResource } from "@/lib/snippets";
import { useSearchParam } from "@/lib/use-search-param";
import { EnableIntegrationDialog } from "./enable-dialog";

type Tab = ProviderTab;

const STATUS_TONES = { beta: "accent", ga: "ok", soon: "neutral" } as const;

export function ProviderView({ slug }: { slug: string }) {
	const provider = getProvider(slug);
	const href = useHref();
	if (!provider) {
		return (
			<PageBody>
				<EmptyState
					action={
						<Link className={buttonVariants()} href={href("/catalog")}>
							Back to catalog
						</Link>
					}
					description={`There's no integration called "${slug}" in the catalog.`}
					title="Integration not found"
				/>
			</PageBody>
		);
	}
	return <ProviderDetail provider={provider} />;
}

function ProviderDetail({ provider }: { provider: Provider }) {
	const { env } = useEnv();
	const href = useHref();
	const tabs = providerTabs(provider.status);
	const [tab, setTab] = useSearchParam<Tab>(
		"tab",
		tabs.map((t) => t.value),
		"overview"
	);
	const [enabling, setEnabling] = useState(false);
	const integrations = env.integrations.filter(
		(i) => i.provider === provider.slug
	);
	const soon = provider.status === "soon";

	return (
		<>
			<div className="border-border bg-background border-b">
				<div className="px-4 pt-6 sm:px-8 md:pt-1">
					{/* Phones only: from md up the sidebar's first row goes back. */}
					<Link
						className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-sm md:hidden"
						href={href("/catalog")}
					>
						<ArrowLeftIcon className="size-3.5" />
						Catalog
					</Link>
					<div className="flex flex-col gap-4 py-6 sm:flex-row sm:items-center sm:justify-between">
						<div className="flex items-center gap-4">
							<ProviderLogo provider={provider} size={56} />
							<div className="grid gap-1.5">
								<div className="flex items-center gap-2">
									<h1 className="tracking-heading text-2xl font-semibold">
										{provider.name}
									</h1>
									<Badge tone={STATUS_TONES[provider.status]}>
										{STATUS_LABELS[provider.status]}
									</Badge>
								</div>
								<p className="text-muted-foreground text-sm">
									{provider.categories.map((c) => CATEGORIES[c]).join(" · ")}
								</p>
							</div>
						</div>
						<div className="flex flex-wrap gap-2">
							{soon ? (
								<Button
									onClick={() =>
										toast.success(
											`We'll email you when ${provider.name} is available`
										)
									}
									variant="primary"
								>
									Request early access
								</Button>
							) : null}
							{!soon && integrations.length > 0 ? (
								<>
									<Link
										className={buttonVariants()}
										href={href(`/integrations/${integrations[0]?.id}`)}
									>
										<CheckIcon />
										Enabled · View integration
									</Link>
									<Link
										className={buttonVariants({ variant: "primary" })}
										href={href(
											`/connections?new=1&integration=${integrations[0]?.id}`
										)}
									>
										<PlusIcon />
										Add connection
									</Link>
								</>
							) : null}
							{!soon && integrations.length === 0 ? (
								<Button onClick={() => setEnabling(true)} variant="primary">
									Enable integration
								</Button>
							) : null}
						</div>
					</div>
					{/* Phones only: from md up the sidebar lists these tabs. */}
					<div className="md:hidden">
						<Tabs
							onChange={setTab}
							tabs={tabs.map((t) => ({ label: t.label, value: t.value }))}
							value={tab}
						/>
					</div>
				</div>
			</div>
			<PageBody>
				{tab === "overview" ? <OverviewTab provider={provider} /> : null}
				{tab === "auth" ? <AuthTab provider={provider} /> : null}
				{tab === "data" ? <DataTab provider={provider} /> : null}
				{tab === "api" ? <ApiTab provider={provider} /> : null}
			</PageBody>
			{soon ? null : (
				<EnableIntegrationDialog
					onOpenChange={setEnabling}
					open={enabling}
					provider={provider}
				/>
			)}
		</>
	);
}

function OverviewTab({ provider }: { provider: Provider }) {
	return (
		<div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
			<div className="grid content-start gap-6">
				<p className="text-prose">{provider.description}</p>
				<Card>
					<CardHeader
						description="Read through the same endpoints as every other tool in the category."
						title="Unified models"
					/>
					{provider.models.length === 0 ? (
						<p className="text-muted-foreground px-5 py-4 text-sm">
							This integration exposes write actions only.
						</p>
					) : (
						<ul className="divide-border divide-y">
							{provider.models.map((m) => (
								<li
									className="flex items-start justify-between gap-4 px-5 py-4"
									key={m}
								>
									<div className="grid gap-1">
										<span className="font-mono text-sm font-medium">
											{MODELS[m].name}
										</span>
										<span className="text-muted-foreground text-sm">
											{MODELS[m].description}
										</span>
									</div>
									<span className="text-muted-foreground shrink-0 font-mono text-xs">
										GET {apiPath(m)}
									</span>
								</li>
							))}
						</ul>
					)}
				</Card>
				{provider.writeActions.length > 0 ? (
					<Card>
						<CardHeader
							description="Asynchronous; you get action.completed or action.failed by webhook."
							title="Write actions"
						/>
						<ul className="divide-border divide-y">
							{provider.writeActions.map((a) => (
								<li
									className="flex items-center justify-between gap-4 px-5 py-3 text-sm"
									key={a.scope}
								>
									<span>{a.name}</span>
									<span className="flex items-center gap-3">
										<span className="text-muted-foreground font-mono text-xs">
											{a.endpoint}
										</span>
										<Badge className="font-mono">{a.scope}</Badge>
									</span>
								</li>
							))}
						</ul>
					</Card>
				) : null}
			</div>
			<aside className="grid content-start gap-4">
				<Card className="p-5">
					<dl className="grid gap-4 text-sm">
						<Meta label="Products" value={provider.products.join(", ")} />
						{provider.status === "soon" ? null : (
							<>
								<Meta
									label="Authentication"
									value={AUTH_LABELS[provider.auth]}
								/>
								<Meta
									label="Sync"
									value="Incremental, every 15 minutes to daily"
								/>
								<Meta label="Vendor rate limit" value={provider.rateLimit} />
								<Meta
									label="Sandbox"
									value={
										<span className="flex items-center gap-1.5">
											<FlaskConicalIcon className="text-ds-accent size-3.5" />
											Generated data, no credentials needed
										</span>
									}
								/>
								<Meta
									label="Passthrough"
									value="Any vendor endpoint, with stored credentials"
								/>
							</>
						)}
					</dl>
				</Card>
				{provider.vendorDocs ? (
					<a
						className="border-border bg-card hover:bg-ds-shell flex items-center justify-between rounded-lg border px-4 py-3 text-sm"
						href={provider.vendorDocs}
						rel="noopener"
						target="_blank"
					>
						{provider.name} API reference
						<ExternalLinkIcon className="text-muted-foreground size-3.5" />
					</a>
				) : null}
			</aside>
		</div>
	);
}

function Meta({ label, value }: { label: string; value: React.ReactNode }) {
	return (
		<div className="grid gap-1">
			<dt className="text-muted-foreground text-xs">{label}</dt>
			<dd>{value}</dd>
		</div>
	);
}

function AuthTab({ provider }: { provider: Provider }) {
	return (
		<div className="grid gap-6 lg:grid-cols-2">
			<Card>
				<CardHeader
					description={`Your customer enters these in SecureFabric Connect. They're validated against ${provider.name} before anything is saved, encrypted with AES-256-GCM, and never returned by the API.`}
					title={
						<span className="flex items-center gap-2">
							<KeyRoundIcon className="text-muted-foreground size-4" />
							{AUTH_LABELS[provider.auth]}
						</span>
					}
				/>
				<Table>
					<thead>
						<tr>
							<Th>Field</Th>
							<Th>Key</Th>
							<Th className="text-right">Type</Th>
						</tr>
					</thead>
					<tbody>
						{provider.fields.map((f) => (
							<Tr key={f.key}>
								<Td>
									<div className="grid gap-0.5 py-2">
										<span>{f.label}</span>
										{f.help ? (
											<span className="text-muted-foreground text-xs">
												{f.help}
											</span>
										) : null}
									</div>
								</Td>
								<Td className="text-code text-muted-foreground font-mono">
									{f.key}
								</Td>
								<Td className="text-right">
									{f.secret ? (
										<Badge>
											<LockIcon className="size-3" />
											Secret
										</Badge>
									) : (
										<Badge>{f.options ? "Select" : "Text"}</Badge>
									)}
								</Td>
							</Tr>
						))}
					</tbody>
				</Table>
			</Card>
			<div className="grid content-start gap-6">
				<Card>
					<CardHeader title="Permissions your customer needs" />
					<ul className="grid gap-3 px-5 py-4 text-sm">
						{provider.permissions.map((p) => (
							<li className="flex gap-2" key={p}>
								<CheckIcon className="text-ds-success mt-0.5 size-4 shrink-0" />
								{p}
							</li>
						))}
					</ul>
				</Card>
				<Card className="p-5">
					<p className="text-sm font-medium">Skip this with a sandbox</p>
					<p className="text-muted-foreground mt-1 text-sm">
						Sandbox connections behave like real ones: same endpoints, same
						models, scheduled syncs and webhooks. The data is generated for{" "}
						<span className="text-code font-mono">{SANDBOX_DOMAIN}</span>, so
						you can build before a customer connects anything.
					</p>
				</Card>
			</div>
		</div>
	);
}

function DataTab({ provider }: { provider: Provider }) {
	const [model, setModel] = useState<ModelKey>(
		provider.models[0] ?? "vulnerabilities"
	);
	const records = generateRecords(
		`catalog:${provider.slug}`,
		provider.slug,
		model,
		SANDBOX_DOMAIN,
		Date.now(),
		3
	);
	const [record] = records;
	if (provider.models.length === 0 || !record) {
		return (
			<p className="text-muted-foreground text-sm">
				No readable models for this integration.
			</p>
		);
	}
	return (
		<div className="grid gap-4">
			<div className="flex flex-wrap items-center justify-between gap-3">
				<p className="text-muted-foreground max-w-2xl text-sm">
					The same record twice: as {provider.name} returns it, and as the
					SecureFabric API returns it. Your code only ever sees the right-hand
					side, whichever tool the customer runs. The original stays available
					under <span className="text-code font-mono">raw</span>.
				</p>
				<div className="w-56">
					<Select
						ariaLabel="Model"
						onChange={setModel}
						options={provider.models.map((m) => ({
							label: MODELS[m].name,
							value: m,
						}))}
						size="sm"
						value={model}
					/>
				</div>
			</div>
			<div className="grid gap-4 lg:grid-cols-2">
				<CodeBlock
					code={JSON.stringify(record.raw, null, 2)}
					json
					maxHeight="32rem"
					title={`${provider.name} response`}
				/>
				<CodeBlock
					code={JSON.stringify(record.unified, null, 2)}
					json
					maxHeight="32rem"
					title={`SecureFabric ${MODELS[model].name}`}
				/>
			</div>
		</div>
	);
}

function ApiTab({ provider }: { provider: Provider }) {
	const { env } = useEnv();
	const conn = env.connections.find((c) => c.provider === provider.slug);
	const [model] = provider.models;
	if (!model) {
		return (
			<p className="text-muted-foreground text-sm">
				This integration exposes write actions only. See Overview.
			</p>
		);
	}
	const path = apiPath(model);
	return (
		<div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
			<div className="grid content-start gap-3 text-sm">
				<p>
					List {MODELS[model].name.toLowerCase()} records for one of your
					customers. Pass the connection in the
					<span className="text-code font-mono"> X-Connection-Id </span>
					header; the response shape is the same for every integration in the
					category.
				</p>
				<ul className="text-muted-foreground grid gap-1">
					<li>
						<span className="text-code text-foreground font-mono">
							updatedSince
						</span>
						: incremental reads, ISO 8601
					</li>
					<li>
						<span className="text-code text-foreground font-mono">limit</span>,{" "}
						<span className="text-code text-foreground font-mono">offset</span>:
						up to 500 per page, or{" "}
						<span className="text-code text-foreground font-mono">
							enableCursor
						</span>{" "}
						for cursor pages
					</li>
					<li>
						<span className="text-code text-foreground font-mono">
							vendor_data
						</span>
						: the vendor's original record, on every response
					</li>
				</ul>
				{conn ? null : (
					<p className="text-muted-foreground text-xs">
						The samples use a placeholder connection ID until you connect an
						account.
					</p>
				)}
			</div>
			<CodeTabs
				samples={samples({
					connectionId: conn?.id ?? "conn_XXXXXXXXXXXX",
					method: "GET",
					path,
					query: { limit: "100" },
					sdk: [sdkResource(path), "list"],
					secretKey: env.keys.secret,
				})}
			/>
		</div>
	);
}
