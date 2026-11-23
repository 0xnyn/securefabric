"use client";

import { CheckIcon, SearchIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { PageBody, PageHeader, ProviderLogo } from "@/components/common";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Select } from "@/components/ui/overlay";
import { Badge, EmptyState, Input } from "@/components/ui/primitives";
import {
	CATEGORIES,
	CATEGORY_ORDER,
	type CategoryKey,
	MODELS,
	PROVIDERS,
	type Provider,
} from "@/lib/catalog";
import { useSearchParam } from "@/lib/use-search-param";

type Availability = "all" | "available" | "soon";

const STATUS_RANK = { beta: 1, ga: 0, soon: 2 } as const;

function ProviderCard({
	provider,
	enabled,
}: {
	provider: Provider;
	enabled: boolean;
}) {
	const href = useHref();
	return (
		<Link
			className="group border-border bg-card hover:border-ds-line-accent hover:bg-ds-shell flex flex-col gap-4 rounded-lg border p-4 transition-colors"
			href={href(`/catalog/${provider.slug}`)}
		>
			<div className="flex items-start justify-between gap-3">
				<ProviderLogo provider={provider} size={40} />
				<div className="flex items-center gap-1.5">
					{enabled ? (
						<Badge tone="ok">
							<CheckIcon className="size-3" />
							Enabled
						</Badge>
					) : null}
					{provider.status === "beta" ? (
						<Badge tone="accent">Beta</Badge>
					) : null}
					{provider.status === "soon" ? <Badge>Coming soon</Badge> : null}
				</div>
			</div>
			<div className="grid gap-1">
				<p className="text-sm font-medium">{provider.name}</p>
				<p className="text-muted-foreground line-clamp-2 text-sm">
					{provider.description}
				</p>
			</div>
			<div className="mt-auto flex flex-wrap gap-1">
				{provider.models.slice(0, 3).map((m) => (
					<span
						className="border-border text-2xs text-muted-foreground rounded border px-1.5 py-0.5 font-mono"
						key={m}
					>
						{MODELS[m].name}
					</span>
				))}
				{provider.models.length === 0 && provider.writeActions.length > 0 ? (
					<span className="border-border text-2xs text-muted-foreground rounded border px-1.5 py-0.5 font-mono">
						Actions
					</span>
				) : null}
			</div>
		</Link>
	);
}

const CATEGORY_VALUES = ["all", ...CATEGORY_ORDER] as const;

export function CatalogView() {
	const { env } = useEnv();
	const [query, setQuery] = useState("");
	const [category, setCategory] = useSearchParam<CategoryKey | "all">(
		"category",
		CATEGORY_VALUES,
		"all"
	);
	const [availability, setAvailability] = useState<Availability>("all");
	const enabled = new Set(env.integrations.map((i) => i.provider));
	const q = query.trim().toLowerCase();

	const matchesText = (p: Provider): boolean =>
		!q ||
		p.name.toLowerCase().includes(q) ||
		p.description.toLowerCase().includes(q) ||
		p.models.some((m) => MODELS[m].name.toLowerCase().includes(q));
	const matchesAvailability = (p: Provider): boolean =>
		availability === "all" ||
		(availability === "soon" ? p.status === "soon" : p.status !== "soon");

	const base = PROVIDERS.filter(
		(p) => matchesText(p) && matchesAvailability(p)
	);
	const visible = base
		.filter((p) => category === "all" || p.categories.includes(category))
		.sort(
			(a, b) =>
				STATUS_RANK[a.status] - STATUS_RANK[b.status] ||
				a.name.localeCompare(b.name)
		);
	const liveCount = PROVIDERS.filter((p) => p.status !== "soon").length;

	return (
		<>
			<PageHeader
				description={
					category === "all"
						? `${PROVIDERS.length} security tools, ${liveCount} available today. Every integration maps into the same unified models, so code written against one scanner works with all of them.`
						: `${visible.length} ${visible.length === 1 ? "tool" : "tools"} in ${CATEGORIES[category]}. Each maps into the same unified models as every other tool.`
				}
				title={category === "all" ? "Catalog" : CATEGORIES[category]}
			/>
			<PageBody>
				{/* The categories are in the sidebar (shell/focused-nav.tsx); the
				    page keeps a picker only for phones, where the sidebar hides. */}
				<div className="grid content-start gap-5">
					<div className="flex flex-col gap-2 sm:flex-row">
						<div className="relative flex-1">
							<SearchIcon className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
							<Input
								aria-label="Search integrations"
								className="pl-9"
								onChange={(e) => setQuery(e.target.value)}
								placeholder="Search by tool or model, e.g. CrowdStrike or Vulnerability"
								value={query}
							/>
						</div>
						<div className="md:hidden">
							<Select
								ariaLabel="Category"
								onChange={(v) => setCategory(v as CategoryKey | "all")}
								options={[
									{ label: "All categories", value: "all" },
									...CATEGORY_ORDER.map((c) => ({
										label: CATEGORIES[c],
										value: c,
									})),
								]}
								value={category}
							/>
						</div>
						<div className="sm:w-44">
							<Select
								ariaLabel="Availability"
								onChange={setAvailability}
								options={[
									{ label: "All tools", value: "all" },
									{ label: "Available now", value: "available" },
									{ label: "Coming soon", value: "soon" },
								]}
								value={availability}
							/>
						</div>
					</div>
					{visible.length === 0 ? (
						<EmptyState
							description="Try another search, or request the tool you need and we'll prioritize it."
							icon={<SearchIcon className="size-4" />}
							title="No integrations match"
						/>
					) : (
						<div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
							{visible.map((p) => (
								<ProviderCard
									enabled={enabled.has(p.slug)}
									key={p.slug}
									provider={p}
								/>
							))}
						</div>
					)}
				</div>
			</PageBody>
		</>
	);
}
