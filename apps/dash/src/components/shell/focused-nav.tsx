"use client";

import { cn } from "@securefabric/ui/lib/utils";
import { ArrowLeftIcon, LayersIcon } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { ProviderLogo } from "@/components/common";
import { useEnv, useHref } from "@/components/shell/env-context";
import {
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	SidebarMenu,
	SidebarMenuBadge,
	SidebarMenuButton,
	SidebarMenuItem,
} from "@/components/ui/sidebar";
import { CATEGORIES, getProvider, PROVIDERS } from "@/lib/catalog";
import { ENDPOINTS } from "@/lib/endpoints";
import { compact } from "@/lib/format";
import {
	CATEGORY_GROUPS,
	CATEGORY_ICONS,
	type Focus,
	providerTabs,
	SETTINGS_SECTIONS,
	settingsSection,
	type TabDef,
} from "@/lib/nav";

/**
 * The way out, first thing in the sidebar. A detail page goes back to its
 * list; a top-level place goes back to the app.
 */
function BackLink({ href, label }: { href: string; label: string }) {
	return (
		<SidebarGroup>
			<SidebarMenu>
				<SidebarMenuItem>
					<SidebarMenuButton
						className="text-muted-foreground hover:text-foreground"
						render={<Link href={href} />}
						tooltip={label}
					>
						<ArrowLeftIcon />
						<span>{label}</span>
					</SidebarMenuButton>
				</SidebarMenuItem>
			</SidebarMenu>
		</SidebarGroup>
	);
}

/** What the sidebar is about: the tool or customer whose sections follow. */
function Identity({
	media,
	title,
	subtitle,
}: {
	media: ReactNode;
	title: string;
	subtitle?: string;
}) {
	return (
		<div className="flex min-w-0 items-center gap-2.5 px-4 pt-1 pb-2 group-data-[collapsible=icon]:hidden">
			{media}
			<div className="grid min-w-0 leading-tight">
				<span className="truncate text-sm font-medium">{title}</span>
				{subtitle ? (
					<span className="text-muted-foreground truncate font-mono text-xs">
						{subtitle}
					</span>
				) : null}
			</div>
		</div>
	);
}

/** A page's tabs as sidebar rows; from md up they replace its tab bar. */
function TabRows({
	base,
	tabs,
	fallback,
	counts = {},
}: {
	base: string;
	tabs: readonly TabDef[];
	fallback: string;
	counts?: Record<string, number>;
}) {
	const params = useSearchParams();
	const current = params.get("tab") ?? fallback;
	return (
		<SidebarMenu>
			{tabs.map((t) => (
				<SidebarMenuItem key={t.value}>
					<SidebarMenuButton
						isActive={current === t.value}
						render={
							<Link
								href={t.value === fallback ? base : `${base}?tab=${t.value}`}
							/>
						}
						tooltip={t.label}
					>
						<t.icon />
						<span>{t.label}</span>
					</SidebarMenuButton>
					{counts[t.value] === undefined ? null : (
						<SidebarMenuBadge>{compact(counts[t.value] ?? 0)}</SidebarMenuBadge>
					)}
				</SidebarMenuItem>
			))}
		</SidebarMenu>
	);
}

function Group({ label, children }: { label?: string; children: ReactNode }) {
	return (
		<SidebarGroup>
			{label ? <SidebarGroupLabel>{label}</SidebarGroupLabel> : null}
			<SidebarGroupContent>{children}</SidebarGroupContent>
		</SidebarGroup>
	);
}

// ---------------------------------------------------------------------------

function SettingsFocus() {
	const href = useHref();
	const { env } = useEnv();
	return (
		<>
			<BackLink href={href()} label="Back to app" />
			<Group label={`Settings · ${env.name}`}>
				<TabRows
					base={href("/settings")}
					fallback={settingsSection(null)}
					tabs={SETTINGS_SECTIONS}
				/>
			</Group>
		</>
	);
}

/**
 * The catalog's categories, here and nowhere else on the page, grouped by
 * job. Every row has an icon, so collapsed to icons the sidebar still lists
 * them all, with the name in the tooltip. Counts are of the whole catalog so
 * they don't jump while you type in the search.
 */
function CatalogFocus() {
	const href = useHref();
	const params = useSearchParams();
	const current = params.get("category");
	return (
		<>
			<BackLink href={href()} label="Back to app" />
			<Group>
				<SidebarMenu>
					<SidebarMenuItem>
						<SidebarMenuButton
							isActive={!current}
							render={<Link href={href("/catalog")} />}
							tooltip="All tools"
						>
							<LayersIcon />
							<span>All tools</span>
						</SidebarMenuButton>
						<SidebarMenuBadge>{PROVIDERS.length}</SidebarMenuBadge>
					</SidebarMenuItem>
				</SidebarMenu>
			</Group>
			{CATEGORY_GROUPS.map((group) => (
				<Group key={group.label} label={group.label}>
					<SidebarMenu>
						{group.categories.map((c) => {
							const Icon = CATEGORY_ICONS[c];
							return (
								<SidebarMenuItem key={c}>
									<SidebarMenuButton
										className="pr-8"
										isActive={current === c}
										render={<Link href={href(`/catalog?category=${c}`)} />}
										tooltip={CATEGORIES[c]}
									>
										<Icon />
										<span className="truncate">{CATEGORIES[c]}</span>
									</SidebarMenuButton>
									<SidebarMenuBadge>
										{PROVIDERS.filter((p) => p.categories.includes(c)).length}
									</SidebarMenuBadge>
								</SidebarMenuItem>
							);
						})}
					</SidebarMenu>
				</Group>
			))}
		</>
	);
}

function ProviderFocus({ id }: { id: string }) {
	const href = useHref();
	const provider = getProvider(id);
	if (!provider) {
		return <BackLink href={href("/catalog")} label="Catalog" />;
	}
	return (
		<>
			<BackLink href={href("/catalog")} label="Catalog" />
			<Identity
				media={<ProviderLogo provider={provider} size={28} />}
				subtitle={provider.slug}
				title={provider.name}
			/>
			<Group>
				<TabRows
					base={href(`/catalog/${provider.slug}`)}
					fallback="overview"
					tabs={providerTabs(provider.status)}
				/>
			</Group>
		</>
	);
}

const METHOD_TONE: Record<string, string> = {
	GET: "text-ds-success-text",
	PATCH: "text-ds-warn-text",
	POST: "text-ds-accent",
};

function PlaygroundFocus() {
	const href = useHref();
	const params = useSearchParams();
	const current = params.get("endpoint") ?? ENDPOINTS[0]?.id;
	const groups = [...new Set(ENDPOINTS.map((e) => e.group))];
	return (
		<>
			<BackLink href={href()} label="Back to app" />
			{groups.map((group) => (
				<Group key={group} label={group}>
					<SidebarMenu className="group-data-[collapsible=icon]:hidden">
						{ENDPOINTS.filter((e) => e.group === group).map((e) => (
							<SidebarMenuItem key={e.id}>
								<SidebarMenuButton
									isActive={current === e.id}
									render={<Link href={href(`/playground?endpoint=${e.id}`)} />}
									title={e.path}
								>
									<span
										className={cn(
											"text-2xs w-9 shrink-0 font-mono font-semibold",
											METHOD_TONE[e.method]
										)}
									>
										{e.method}
									</span>
									<span className="truncate">{e.title}</span>
								</SidebarMenuButton>
							</SidebarMenuItem>
						))}
					</SidebarMenu>
				</Group>
			))}
		</>
	);
}

/**
 * The sidebar for a place that takes it over. One switch, so the rule for
 * which places do is readable in one spot (`focusOf` in lib/nav.ts).
 */
export function FocusedNav({ focus }: { focus: Focus }) {
	switch (focus.kind) {
		case "settings":
			return <SettingsFocus />;
		case "catalog":
			return <CatalogFocus />;
		case "playground":
			return <PlaygroundFocus />;
		case "provider":
			return <ProviderFocus id={focus.id} />;
		default:
			return null;
	}
}
