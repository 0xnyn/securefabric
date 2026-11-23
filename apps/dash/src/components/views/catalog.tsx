"use client";

import { unwrap } from "@securefabric/client";
import { Badge } from "@securefabric/ui/components/badge";
import { Button } from "@securefabric/ui/components/button";
import { Card } from "@securefabric/ui/components/card";
import { Input } from "@securefabric/ui/components/form";
import { Select } from "@securefabric/ui/components/select";
import { Tooltip } from "@securefabric/ui/components/tooltip";
import { cn } from "@securefabric/ui/lib/utils";
import { PageBody } from "@securefabric/ui/patterns/page";
import { Section } from "@securefabric/ui/patterns/section";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	ArrowUpRightIcon,
	CheckIcon,
	ClockIcon,
	KeyRoundIcon,
	SearchIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Gated } from "@/components/domain/access";
import { ConnectorLogo } from "@/components/domain/connector-logo";
import { errorText, QueryState } from "@/components/domain/query-state";
import { useAccess, useEnv, useHref } from "@/components/shell/env-context";
import { api } from "@/lib/api";
import {
	authLabel,
	CATEGORIES,
	type CategoryId,
	categoryOf,
	connectSentence,
	DELETION_LABELS,
	everySeconds,
	PLANNED,
	type PlannedConnector,
	RELEASES,
	type Release,
	SYNC_MODE_LABELS,
	typeLabel,
} from "@/lib/connector-catalog";
import type { Connector } from "@/lib/types";
import { useSearchParam } from "@/lib/use-search-param";

// ---------------------------------------------------------------------------
// Data

interface StreamInfo {
	capabilities?: Record<string, { supported: boolean; notes?: string | null }>;
	cost?: string | null;
	deletion: string;
	enabled_by_default?: boolean;
	finding_types: string[];
	interval: { default: number; max: number; min: number };
	name: string;
	object: string;
	resource_types: string[];
	sync_mode: string;
	title: string;
	webhook_events?: string[];
}

function streamsOf(c: Connector): StreamInfo[] {
	return c.streams as unknown as StreamInfo[];
}

/** Resource and finding types across every stream, without repeats. */
function syncedTypes(c: Connector): {
	findings: string[];
	resources: string[];
} {
	const findings = new Set<string>();
	const resources = new Set<string>();
	for (const s of streamsOf(c)) {
		for (const t of s.finding_types) {
			findings.add(t);
		}
		for (const t of s.resource_types) {
			resources.add(t);
		}
	}
	return { findings: [...findings], resources: [...resources] };
}

function vendorOf(c: Connector): string {
	return c.name.split(" ")[0] ?? c.name;
}

function useConnectors() {
	return useQuery({
		queryFn: () => unwrap(api.GET("/v1/connectors")),
		queryKey: ["connectors"],
		staleTime: 5 * 60_000,
	});
}

/** Integrations in this environment, keyed by connector, when the role can read them. */
function useEnabled(): Map<string, string> {
	const { client, env } = useEnv();
	const access = useAccess();
	const integrations = useQuery({
		enabled: access.can("provisioning:read"),
		queryFn: () => unwrap(client.GET("/v1/integrations")),
		queryKey: ["integrations", env.id],
	});
	return new Map(
		(integrations.data ?? []).map((i) => [i.connector_id, i.id] as const)
	);
}

// ---------------------------------------------------------------------------
// List

type CategoryFilter = "all" | CategoryId;
type AvailabilityFilter = "all" | "available" | "planned";

const CATEGORY_FILTERS: CategoryFilter[] = [
	"all",
	...CATEGORIES.map((c) => c.id),
];
const AVAILABILITY_FILTERS: AvailabilityFilter[] = [
	"all",
	"available",
	"planned",
];
const RELEASE_ORDER: Release[] = ["february", "partner", "spring", "detection"];

function matches(q: string, ...fields: (string | undefined)[]): boolean {
	const needle = q.trim().toLowerCase();
	return (
		needle === "" ||
		fields.some((f) => f?.toLowerCase().includes(needle) ?? false)
	);
}

export function CatalogView() {
	const connectors = useConnectors();
	const enabled = useEnabled();
	const [q, setQ] = useState("");
	const [category, setCategory] = useSearchParam<CategoryFilter>(
		"category",
		CATEGORY_FILTERS,
		"all"
	);
	const [availability, setAvailability] = useSearchParam<AvailabilityFilter>(
		"show",
		AVAILABILITY_FILTERS,
		"all"
	);

	const live = connectors.data ?? [];
	const liveIds = new Set(live.map((c) => c.id));
	const planned = PLANNED.filter((p) => !liveIds.has(p.id));

	const liveShown = live.filter(
		(c) =>
			(category === "all" || categoryOf(c.categories) === category) &&
			matches(q, c.name, c.id, c.description, ...c.categories)
	);
	const plannedShown = planned.filter(
		(p) =>
			(category === "all" || p.category === category) &&
			matches(q, p.name, p.id, p.vendor, p.description)
	);
	const showLive = availability !== "planned";
	const showPlanned = availability !== "available";
	const nothing =
		(showLive ? liveShown.length : 0) +
			(showPlanned ? plannedShown.length : 0) ===
		0;

	const countFor = (id: CategoryFilter) =>
		(showLive
			? live.filter((c) => id === "all" || categoryOf(c.categories) === id)
					.length
			: 0) +
		(showPlanned
			? planned.filter((p) => id === "all" || p.category === id).length
			: 0);

	return (
		<>
			<div className="border-border bg-background border-b">
				<div className="grid gap-5 px-4 pt-7 pb-5 sm:px-8">
					<div className="grid gap-1.5">
						<h1 className="tracking-heading text-2xl font-semibold">Catalog</h1>
						<p className="text-muted-foreground max-w-2xl text-sm">
							Security tools your customers can connect, all through one
							findings and resources API.
						</p>
					</div>
					<div className="flex flex-col gap-2 sm:flex-row sm:items-center">
						<div className="relative w-full sm:max-w-xs">
							<SearchIcon className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
							<Input
								aria-label="Search the catalog"
								className="pl-9"
								onChange={(e) => setQ(e.target.value)}
								placeholder="Search by name or vendor"
								type="search"
								value={q}
							/>
						</div>
						<Select
							ariaLabel="Category"
							className="sm:w-56"
							onChange={setCategory}
							options={CATEGORY_FILTERS.filter(
								(id) => id === "all" || countFor(id) > 0
							).map((id) => ({
								label:
									id === "all"
										? `All categories (${countFor(id)})`
										: `${CATEGORIES.find((c) => c.id === id)?.label ?? id} (${countFor(id)})`,
								value: id,
							}))}
							value={category}
						/>
						<Select
							ariaLabel="Availability"
							className="sm:w-44"
							onChange={setAvailability}
							options={[
								{ label: "All connectors", value: "all" },
								{ label: "Available now", value: "available" },
								{ label: "Coming soon", value: "planned" },
							]}
							value={availability}
						/>
					</div>
				</div>
			</div>
			<PageBody className="grid gap-10">
				<QueryState
					empty={{
						action: (
							<Button
								onClick={() => {
									setQ("");
									setCategory("all");
									setAvailability("all");
								}}
								size="sm"
							>
								Clear filters
							</Button>
						),
						description: "Try a different name, or clear the filters.",
						title: "No matching connectors",
						when: nothing,
					}}
					query={connectors}
					rows={6}
				>
					{showLive && liveShown.length > 0 ? (
						<Section
							description="Turn one on, then send your customers a connect link."
							title="Available now"
						>
							<div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
								{liveShown.map((c) => (
									<LiveCard
										connector={c}
										enabled={enabled.has(c.id)}
										key={c.id}
									/>
								))}
							</div>
						</Section>
					) : null}
					{showPlanned
						? RELEASE_ORDER.map((release) => {
								const items = plannedShown.filter((p) => p.release === release);
								if (items.length === 0) {
									return null;
								}
								return (
									<Section
										description={RELEASES[release].detail}
										key={release}
										title={RELEASES[release].label}
									>
										<div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
											{items.map((p) => (
												<PlannedCard connector={p} key={p.id} />
											))}
										</div>
									</Section>
								);
							})
						: null}
				</QueryState>
			</PageBody>
		</>
	);
}

function TypeChips({ types: all, max = 4 }: { types: string[]; max?: number }) {
	// A stream can name the same type as a resource and a finding (HOST).
	const types = [...new Set(all)];
	const shown = types.slice(0, max);
	const rest = types.length - shown.length;
	return (
		<div className="flex flex-wrap gap-1.5">
			{shown.map((t) => (
				<Badge key={t}>{typeLabel(t)}</Badge>
			))}
			{rest > 0 ? (
				<Tooltip content={types.slice(max).map(typeLabel).join(", ")}>
					<Badge>+{rest} more</Badge>
				</Tooltip>
			) : null}
		</div>
	);
}

function LiveCard({
	connector: c,
	enabled,
}: {
	connector: Connector;
	enabled: boolean;
}) {
	const href = useHref();
	const { findings, resources } = syncedTypes(c);
	const category = CATEGORIES.find((x) => x.id === categoryOf(c.categories));
	return (
		<Link className="group block" href={href(`/catalog/${c.id}`)}>
			<Card className="group-hover:border-foreground/20 group-focus-visible:ring-ring/40 grid h-full content-start gap-4 p-5 transition-[border-color,box-shadow] group-hover:shadow-sm group-focus-visible:ring-2">
				<div className="flex items-start gap-3">
					<ConnectorLogo id={c.id} logo={c.logo_url} name={c.name} size={40} />
					<div className="grid min-w-0 flex-1 gap-0.5">
						<span className="truncate font-medium">{c.name}</span>
						<span className="text-muted-foreground truncate text-xs">
							{category?.label}
						</span>
					</div>
					<LiveBadge beta={c.status === "beta"} enabled={enabled} />
				</div>
				<p className="text-muted-foreground line-clamp-2 text-sm">
					{c.description}
				</p>
				<div className="mt-auto grid gap-3">
					<TypeChips
						types={[
							...resources,
							...findings.filter((f) => !resources.includes(f)),
						]}
					/>
					<div className="text-muted-foreground flex items-center justify-between border-t pt-3 text-xs">
						<span className="inline-flex items-center gap-1.5">
							<KeyRoundIcon className="size-3" />
							{authLabel(String(c.auth.mode))}
						</span>
						<span className="group-hover:text-foreground inline-flex items-center gap-1 transition-colors">
							Details <ArrowUpRightIcon className="size-3" />
						</span>
					</div>
				</div>
			</Card>
		</Link>
	);
}

function LiveBadge({ enabled, beta }: { enabled: boolean; beta: boolean }) {
	if (enabled) {
		return (
			<Badge tone="ok">
				<CheckIcon className="size-3" />
				On
			</Badge>
		);
	}
	return beta ? <Badge tone="accent">Beta</Badge> : null;
}

function PlannedCard({ connector: p }: { connector: PlannedConnector }) {
	const href = useHref();
	const category = CATEGORIES.find((x) => x.id === p.category);
	return (
		<Link className="group block" href={href(`/catalog/${p.id}`)}>
			<Card className="bg-muted/30 group-hover:border-foreground/15 grid h-full content-start gap-4 border-dashed p-5 transition-colors">
				<div className="flex items-start gap-3">
					<ConnectorLogo id={p.id} muted name={p.name} size={40} />
					<div className="grid min-w-0 flex-1 gap-0.5">
						<span className="text-foreground/80 truncate font-medium">
							{p.name}
						</span>
						<span className="text-muted-foreground truncate text-xs">
							{category?.label}
						</span>
					</div>
					<Badge>
						<ClockIcon className="size-3" />
						Coming soon
					</Badge>
				</div>
				<p className="text-muted-foreground line-clamp-2 text-sm">
					{p.description}
				</p>
				<div className="mt-auto opacity-75">
					<TypeChips
						types={[
							...p.resources,
							...p.findings.filter((f) => !p.resources.includes(f)),
						]}
					/>
				</div>
			</Card>
		</Link>
	);
}

// ---------------------------------------------------------------------------
// Detail

export function ConnectorView({ id }: { id: string }) {
	// The list says whether this id is live; only then ask for its manifest, so
	// a planned connector's page doesn't make a request that 404s.
	const list = useConnectors();
	const live = list.data?.some((c) => c.id === id) ?? false;
	const planned = PLANNED.find((p) => p.id === id);
	const connector = useQuery({
		enabled: list.isSuccess && (live || !planned),
		queryFn: () =>
			unwrap(
				api.GET("/v1/connectors/{connector_id}", {
					params: { path: { connector_id: id } },
				})
			),
		queryKey: ["connectors", id],
		retry: false,
	});
	if (list.isSuccess && !live && planned) {
		return <PlannedConnectorView connector={planned} />;
	}
	return (
		<QueryState query={list.isSuccess ? connector : list} rows={6}>
			{connector.data ? <LiveConnectorView connector={connector.data} /> : null}
		</QueryState>
	);
}

function DetailHero({
	id,
	logo,
	name,
	description,
	badges,
	actions,
	muted = false,
}: {
	id: string;
	logo?: string | null;
	name: string;
	description: string;
	badges: React.ReactNode;
	actions: React.ReactNode;
	muted?: boolean;
}) {
	return (
		<div className="border-border bg-background border-b">
			<div className="flex flex-col gap-6 px-4 py-8 sm:px-8 lg:flex-row lg:items-start lg:justify-between">
				<div className="flex min-w-0 gap-5">
					<ConnectorLogo
						id={id}
						logo={logo}
						muted={muted}
						name={name}
						size={64}
					/>
					<div className="grid min-w-0 content-start gap-2">
						<div className="flex flex-wrap items-center gap-2">
							<h1 className="tracking-heading text-2xl font-semibold">
								{name}
							</h1>
							{badges}
						</div>
						<p className="text-muted-foreground max-w-2xl text-sm">
							{description}
						</p>
					</div>
				</div>
				<div className="flex shrink-0 flex-wrap items-center gap-2">
					{actions}
				</div>
			</div>
		</div>
	);
}

function Facts({
	items,
}: {
	items: { label: string; value: React.ReactNode }[];
}) {
	return (
		<Card className="grid content-start divide-y">
			{items.map((f) => (
				<div className="grid gap-1 px-5 py-3.5" key={f.label}>
					<dt className="text-muted-foreground text-xs">{f.label}</dt>
					<dd className="text-sm">{f.value}</dd>
				</div>
			))}
		</Card>
	);
}

function LiveConnectorView({ connector: c }: { connector: Connector }) {
	const { client, env } = useEnv();
	const router = useRouter();
	const href = useHref();
	const queryClient = useQueryClient();
	const enabled = useEnabled();
	const existing = enabled.get(c.id);
	const streams = streamsOf(c);
	const titles = new Map(streams.map((s) => [s.name, s.title]));
	const { findings, resources } = syncedTypes(c);
	const vendor = vendorOf(c);
	const enable = useMutation({
		mutationFn: () =>
			unwrap(client.POST("/v1/integrations", { body: { connector_id: c.id } })),
		onError: (e) =>
			toast.error(`Couldn't turn on ${c.name}`, { description: errorText(e) }),
		onSuccess: async (i) => {
			await queryClient.invalidateQueries({
				queryKey: ["integrations", env.id],
			});
			toast.success(`${i.display_name} is on in ${env.name}`);
			router.push(href(`/integrations/${i.id}`));
		},
	});
	const capabilityRows = streams.flatMap((s) =>
		Object.entries(s.capabilities ?? {}).map(([field, cap]) => ({
			field,
			notes: cap.notes ?? null,
			stream: s.title,
			supported: cap.supported,
		}))
	);
	return (
		<>
			<DetailHero
				actions={
					<>
						{c.docs_url ? (
							<Button
								render={<a href={c.docs_url} rel="noopener" target="_blank" />}
							>
								Setup guide <ArrowUpRightIcon />
							</Button>
						) : null}
						{existing ? (
							<Button
								render={<Link href={href(`/integrations/${existing}`)} />}
								variant="primary"
							>
								Open integration
							</Button>
						) : (
							<Gated requires={{ scope: "provisioning:write" }}>
								<Button
									disabled={enable.isPending}
									onClick={() => enable.mutate()}
									variant="primary"
								>
									{enable.isPending ? "Turning on…" : `Turn on in ${env.name}`}
								</Button>
							</Gated>
						)}
					</>
				}
				badges={
					<>
						{existing ? (
							<Badge tone="ok">
								<CheckIcon className="size-3" /> On
							</Badge>
						) : null}
						{c.status === "beta" ? <Badge tone="accent">Beta</Badge> : null}
						{c.status === "deprecated" ? (
							<Badge tone="warn">Deprecated</Badge>
						) : null}
					</>
				}
				description={c.description}
				id={c.id}
				logo={c.logo_url}
				name={c.name}
			/>
			<PageBody className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
				<div className="grid min-w-0 gap-10">
					<Section
						description="Each stream reads one kind of record from the vendor on its own schedule."
						title="What it syncs"
					>
						<div className="grid gap-3 md:grid-cols-2">
							{streams.map((s) => (
								<Card className="grid content-start gap-3 p-4" key={s.name}>
									<div className="flex items-center justify-between gap-2">
										<span className="font-medium">{s.title}</span>
										<Badge
											tone={s.object === "resource" ? "neutral" : "accent"}
										>
											{s.object === "resource" ? "Resources" : "Findings"}
										</Badge>
									</div>
									<TypeChips
										max={6}
										types={[...s.resource_types, ...s.finding_types]}
									/>
									<ul className="text-muted-foreground grid gap-1 text-xs">
										<li>
											Syncs {everySeconds(s.interval.default)} by default (
											{everySeconds(s.interval.min).replace("every ", "")} to{" "}
											{everySeconds(s.interval.max).replace("every ", "")})
										</li>
										<li>{SYNC_MODE_LABELS[s.sync_mode] ?? s.sync_mode}</li>
										<li>{DELETION_LABELS[s.deletion] ?? s.deletion}</li>
										{s.webhook_events?.length ? (
											<li>Updates in real time from vendor webhooks</li>
										) : null}
									</ul>
								</Card>
							))}
						</div>
					</Section>
					<Section
						description={`What your customer grants in ${vendor}. Read-only unless marked.`}
						title="Permissions"
					>
						<Card className="divide-y">
							{c.permissions.map((p) => {
								const usedBy = [
									...((p.streams as string[] | undefined) ?? []).map(
										(s) => titles.get(s) ?? s
									),
									...((p.actions as string[] | undefined) ?? []),
								];
								return (
									<div
										className="flex flex-col gap-1 px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between"
										key={`${String(p.name)}:${String(p.access)}`}
									>
										<div className="flex items-center gap-2">
											<span className="text-sm font-medium">
												{String(p.name)}
											</span>
											{p.access === "write" ? (
												<Badge tone="warn">Read and write</Badge>
											) : null}
											{p.optional ? <Badge>Optional</Badge> : null}
										</div>
										{usedBy.length ? (
											<span className="text-muted-foreground text-xs">
												Used for {usedBy.join(", ")}
											</span>
										) : null}
									</div>
								);
							})}
						</Card>
					</Section>
					{capabilityRows.length ? (
						<Section
							description="Fields this connector fills in. The rest stay empty, never guessed."
							title="Field coverage"
						>
							<Card className="divide-y">
								{capabilityRows.map((r) => (
									<div
										className="flex items-start gap-3 px-5 py-3"
										key={`${r.stream}.${r.field}`}
									>
										<span
											className={cn(
												"mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full",
												r.supported
													? "bg-ds-success/15 text-ds-success-text"
													: "bg-muted text-muted-foreground"
											)}
										>
											{r.supported ? <CheckIcon className="size-3" /> : "–"}
										</span>
										<div className="grid gap-0.5">
											<span className="font-mono text-xs">{r.field}</span>
											<span className="text-muted-foreground text-xs">
												{r.stream}
												{r.notes ? ` · ${r.notes}` : ""}
											</span>
										</div>
									</div>
								))}
							</Card>
						</Section>
					) : null}
				</div>
				<aside className="grid gap-4 lg:sticky lg:top-6">
					<Facts
						items={[
							{
								label: "Category",
								value:
									CATEGORIES.find((x) => x.id === categoryOf(c.categories))
										?.label ?? "—",
							},
							{ label: "Connects with", value: authLabel(String(c.auth.mode)) },
							{
								label: "Your customer",
								value: connectSentence(String(c.auth.connect), vendor),
							},
							...(c.auth.vendor_app === "required"
								? [
										{
											label: "Before you start",
											value: `Register your own ${vendor} app, then add it to the integration.`,
										},
									]
								: []),
							{
								label: "Produces",
								value: (
									<TypeChips
										max={8}
										types={[
											...resources,
											...findings.filter((f) => !resources.includes(f)),
										]}
									/>
								),
							},
							...(c.regions.length
								? [
										{
											label: "Regions",
											value: c.regions.map((r) => r.label ?? r.id).join(", "),
										},
									]
								: []),
							{
								label: "Version",
								value: <span className="font-mono text-xs">{c.version}</span>,
							},
						]}
					/>
				</aside>
			</PageBody>
		</>
	);
}

function PlannedConnectorView({
	connector: p,
}: {
	connector: PlannedConnector;
}) {
	const href = useHref();
	const release = RELEASES[p.release];
	const category = CATEGORIES.find((x) => x.id === p.category);
	return (
		<>
			<DetailHero
				actions={
					<>
						<Button render={<Link href={href("/catalog?show=planned")} />}>
							See what else is coming
						</Button>
						<Button disabled variant="primary">
							Not available yet
						</Button>
					</>
				}
				badges={
					<Badge>
						<ClockIcon className="size-3" /> {release.label}
					</Badge>
				}
				description={p.description}
				id={p.id}
				muted
				name={p.name}
			/>
			<PageBody className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
				<div className="grid min-w-0 gap-10">
					<Card className="bg-muted/30 border-dashed p-5 text-sm">
						<p className="font-medium">We're building this connector</p>
						<p className="text-muted-foreground mt-1">
							{release.detail} It will use the same findings and resources API,
							so your code won't need to change.
						</p>
					</Card>
					<Section title="What it will sync">
						<div className="grid gap-3 md:grid-cols-2">
							<Card className="grid gap-3 p-4">
								<span className="font-medium">Resources</span>
								<TypeChips max={8} types={p.resources} />
							</Card>
							<Card className="grid gap-3 p-4">
								<span className="font-medium">Findings</span>
								{p.findings.length ? (
									<TypeChips max={8} types={p.findings} />
								) : (
									<span className="text-muted-foreground text-sm">
										Detections and posture findings, in a new object type
									</span>
								)}
							</Card>
						</div>
					</Section>
				</div>
				<aside className="grid gap-4 lg:sticky lg:top-6">
					<Facts
						items={[
							{ label: "Category", value: category?.label ?? "—" },
							{ label: "Vendor", value: p.vendor },
							{ label: "Your customer will need", value: p.auth },
							{ label: "Availability", value: release.label },
						]}
					/>
				</aside>
			</PageBody>
		</>
	);
}
