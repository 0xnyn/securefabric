"use client";

import {
	ArrowRightIcon,
	BoxesIcon,
	CopyIcon,
	KeyboardIcon,
	LayersIcon,
	MoonIcon,
	PanelLeftIcon,
	PlusIcon,
	RefreshCwIcon,
	RotateCcwIcon,
	ScrollTextIcon,
	SunIcon,
	TerminalIcon,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import type { ReactNode } from "react";
import { toast } from "sonner";
import { ProviderLogo } from "@/components/common";
import { useEnv, useHref } from "@/components/shell/env-context";
import {
	Command,
	CommandDialog,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
	CommandSeparator,
	CommandShortcut,
} from "@/components/ui/command";
import { useSidebar } from "@/components/ui/sidebar";
import { getProvider, PROVIDERS } from "@/lib/catalog";
import { ENDPOINTS } from "@/lib/endpoints";
import { LOG_VIEWS } from "@/lib/log-views";
import { NAV_ITEMS, SETTINGS_SECTIONS } from "@/lib/nav";
import { resetPlayground, triggerSync } from "@/lib/store";
import { HEALTH } from "@/lib/types";
import { useCommandStore } from "./command-store";
import { ShortcutKeys } from "./shortcut-keys";

/** The catalog has ~70 tools: noise under a heading nobody scrolled to,
 * but the fastest way to reach one once two letters are typed. */
const CATALOG_MIN_QUERY = 2;

/** A prefix match on the label beats a substring buried in the keywords. */
function score(value: string, search: string, keywords?: string[]): number {
	const needle = search.trim().toLowerCase();
	if (!needle) {
		return 1;
	}
	const haystack = value.toLowerCase();
	if (haystack.startsWith(needle)) {
		return 1;
	}
	if (haystack.includes(needle)) {
		return 0.7;
	}
	return keywords?.some((k) => k.toLowerCase().includes(needle)) ? 0.4 : 0;
}

/**
 * Items relevant to the page you're on, listed first. Someone pressing ⌘K
 * on a connection most likely wants to do something to that connection.
 */
function useSuggestions(
	run: (fn: () => void) => void,
	go: (path: string) => void
) {
	const pathname = usePathname();
	const { env } = useEnv();
	const [, , section, id] = pathname.split("/");
	const items: {
		id: string;
		label: string;
		icon: ReactNode;
		onSelect: () => void;
	}[] = [];

	if (section === "connections" && id) {
		const conn = env.connections.find((c) => c.id === id);
		if (conn) {
			items.push(
				{
					icon: <RefreshCwIcon />,
					id: "sync",
					label: `Sync ${conn.customer.orgName} now`,
					onSelect: () =>
						run(() => {
							triggerSync(env.slug, conn.id);
							toast.success("Sync started");
						}),
				},
				{
					icon: <ScrollTextIcon />,
					id: "logs",
					label: "Open this connection's logs",
					onSelect: () => go(`/logs?connection=${conn.id}`),
				},
				{
					icon: <TerminalIcon />,
					id: "try",
					label: "Try the API with this connection",
					onSelect: () => go(`/playground?connection=${conn.id}`),
				},
				{
					icon: <CopyIcon />,
					id: "copy",
					label: "Copy connection ID",
					onSelect: () =>
						run(() => {
							navigator.clipboard.writeText(conn.id);
							toast.success("Connection ID copied");
						}),
				}
			);
		}
	}
	if (section === "logs") {
		for (const view of LOG_VIEWS.slice(1, 4)) {
			items.push({
				icon: <view.icon />,
				id: `view:${view.id}`,
				label: `Show ${view.label.toLowerCase()}`,
				onSelect: () => go(`/logs?${view.query}`),
			});
		}
	}
	if (section === "integrations" && id) {
		items.push({
			icon: <PlusIcon />,
			id: "add",
			label: `Add a connection to ${id}`,
			onSelect: () => go(`/connections?new=1&integration=${id}`),
		});
	}
	return items;
}

function Item({
	value,
	keywords,
	icon,
	onSelect,
	children,
	shortcut,
	hint,
}: {
	value: string;
	keywords?: string[];
	icon: ReactNode;
	onSelect: () => void;
	children: ReactNode;
	shortcut?: string;
	hint?: ReactNode;
}) {
	return (
		<CommandItem keywords={keywords} onSelect={onSelect} value={value}>
			{icon}
			<span className="min-w-0 flex-1 truncate">{children}</span>
			{hint ? (
				<span className="text-muted-foreground shrink-0 text-xs">{hint}</span>
			) : null}
			{shortcut ? (
				<CommandShortcut>
					<ShortcutKeys id={shortcut} />
				</CommandShortcut>
			) : null}
		</CommandItem>
	);
}

/**
 * ⌘K: the fastest path to anything.
 *
 * Built on cmdk, which gets the tedious parts right (filtering, the arrow
 * loop across groups, keeping the selection in view). What's left is
 * deciding what belongs in the list, and in what order: what fits this page,
 * then commands (someone typing "new" wants to make something), then places,
 * then the things in this environment by name.
 */
export function CommandPalette() {
	const { open, setOpen, query, setQuery, setHelpOpen, setCreateEnvOpen } =
		useCommandStore();
	const router = useRouter();
	const href = useHref();
	const { env, workspace } = useEnv();
	const { resolvedTheme, setTheme } = useTheme();
	const { toggleSidebar } = useSidebar();

	const run = (fn: () => void): void => {
		setOpen(false);
		fn();
	};
	const go = (path: string): void => run(() => router.push(href(path)));
	const suggestions = useSuggestions(run, go);
	const searchingCatalog = query.trim().length >= CATALOG_MIN_QUERY;

	return (
		<CommandDialog
			className="sm:max-w-xl"
			description="Search pages, connections, integrations and commands"
			onOpenChange={setOpen}
			open={open}
			title="Command palette"
		>
			<Command filter={score} loop>
				<CommandInput
					onValueChange={setQuery}
					placeholder="Search or jump to…"
					value={query}
				/>
				<CommandList className="max-h-[min(26rem,60svh)]">
					<CommandEmpty>Nothing matches “{query}”.</CommandEmpty>

					{suggestions.length > 0 ? (
						<CommandGroup heading="Suggested">
							{suggestions.map((s) => (
								<Item
									icon={s.icon}
									key={s.id}
									onSelect={s.onSelect}
									value={s.label}
								>
									{s.label}
								</Item>
							))}
						</CommandGroup>
					) : null}

					<CommandGroup heading="Commands">
						<Item
							icon={<PlusIcon />}
							keywords={["new", "create", "sandbox"]}
							onSelect={() => go("/connections?new=1")}
							value="Add connection"
						>
							Add connection
						</Item>
						<Item
							icon={<BoxesIcon />}
							keywords={["new", "enable", "catalog"]}
							onSelect={() => go("/catalog")}
							value="Enable an integration"
						>
							Enable an integration
						</Item>
						<Item
							icon={<LayersIcon />}
							keywords={["new", "staging", "production"]}
							onSelect={() => setCreateEnvOpen(true)}
							value="Create environment"
						>
							Create environment
						</Item>
						<Item
							icon={resolvedTheme === "dark" ? <SunIcon /> : <MoonIcon />}
							keywords={["dark", "light", "appearance", "theme"]}
							onSelect={() =>
								run(() => setTheme(resolvedTheme === "dark" ? "light" : "dark"))
							}
							shortcut="theme"
							value="Toggle theme"
						>
							Switch to {resolvedTheme === "dark" ? "light" : "dark"} theme
						</Item>
						<Item
							icon={<PanelLeftIcon />}
							keywords={["collapse", "expand", "navigation"]}
							onSelect={() => run(toggleSidebar)}
							shortcut="sidebar"
							value="Toggle sidebar"
						>
							Toggle sidebar
						</Item>
						<Item
							icon={<KeyboardIcon />}
							keywords={["help", "keys", "hotkeys"]}
							onSelect={() => setHelpOpen(true)}
							shortcut="help"
							value="Keyboard shortcuts"
						>
							Keyboard shortcuts
						</Item>
						<Item
							icon={<CopyIcon />}
							keywords={["api key", "sk_", "token"]}
							onSelect={() =>
								run(() => {
									navigator.clipboard.writeText(env.keys.secret);
									toast.success(`${env.name} secret key copied`);
								})
							}
							value="Copy secret key"
						>
							Copy {env.name} secret key
						</Item>
						<Item
							icon={<RotateCcwIcon />}
							keywords={["reset", "seed", "clear"]}
							onSelect={() =>
								run(() => {
									resetPlayground();
									router.push("/dev");
									toast.success("Workspace reset");
								})
							}
							value="Reset workspace"
						>
							Reset workspace
						</Item>
					</CommandGroup>

					<CommandSeparator />
					<CommandGroup heading="Go to">
						{NAV_ITEMS.map((item) => (
							<Item
								icon={<item.icon />}
								key={item.href}
								keywords={[item.description]}
								onSelect={() => go(item.href)}
								shortcut={`go:${item.href || "/"}`}
								value={item.label}
							>
								{item.label}
							</Item>
						))}
					</CommandGroup>

					{env.connections.length > 0 ? (
						<CommandGroup heading="Connections">
							{env.connections.map((c) => (
								<Item
									hint={HEALTH[c.health].label}
									icon={<ProviderLogo provider={c.provider} size={16} />}
									key={c.id}
									keywords={[
										c.id,
										c.customer.email,
										c.integrationId,
										"connection",
									]}
									onSelect={() => go(`/connections/${c.id}`)}
									value={c.customer.orgName}
								>
									{c.customer.orgName}
								</Item>
							))}
						</CommandGroup>
					) : null}

					{env.integrations.length > 0 ? (
						<CommandGroup heading="Integrations">
							{env.integrations.map((i) => (
								<Item
									hint={getProvider(i.provider)?.name}
									icon={<ProviderLogo provider={i.provider} size={16} />}
									key={i.id}
									keywords={[
										getProvider(i.provider)?.name ?? "",
										"integration",
									]}
									onSelect={() => go(`/integrations/${i.id}`)}
									value={i.id}
								>
									<span className="font-mono">{i.id}</span>
								</Item>
							))}
						</CommandGroup>
					) : null}

					<CommandGroup heading="Log views">
						{LOG_VIEWS.map((v) => (
							<Item
								icon={<v.icon />}
								key={v.id}
								keywords={[v.description, "logs"]}
								onSelect={() => go(`/logs${v.query ? `?${v.query}` : ""}`)}
								value={`Logs: ${v.label}`}
							>
								Logs: {v.label}
							</Item>
						))}
					</CommandGroup>

					<CommandGroup heading="API endpoints">
						{ENDPOINTS.map((e) => (
							<Item
								hint={<span className="font-mono">{e.method}</span>}
								icon={<TerminalIcon />}
								key={e.id}
								keywords={[e.path, e.description, "api", "endpoint"]}
								onSelect={() => go(`/playground?endpoint=${e.id}`)}
								value={e.title}
							>
								{e.title}
							</Item>
						))}
					</CommandGroup>

					{searchingCatalog ? (
						<CommandGroup heading="Catalog">
							{PROVIDERS.map((p) => (
								<Item
									hint={p.status === "soon" ? "Coming soon" : undefined}
									icon={<ProviderLogo provider={p} size={16} />}
									key={p.slug}
									keywords={[p.description, ...p.categories]}
									onSelect={() => go(`/catalog/${p.slug}`)}
									value={p.name}
								>
									{p.name}
								</Item>
							))}
						</CommandGroup>
					) : null}

					<CommandGroup heading="Settings">
						{SETTINGS_SECTIONS.map((s) => (
							<Item
								icon={<s.icon />}
								key={s.value}
								keywords={[s.description, "settings"]}
								onSelect={() => go(`/settings?tab=${s.value}`)}
								value={`Settings: ${s.label}`}
							>
								{s.label}
								<span className="text-muted-foreground"> · Settings</span>
							</Item>
						))}
					</CommandGroup>

					{workspace.environments.length > 1 ? (
						<CommandGroup heading="Switch environment">
							{workspace.environments
								.filter((e) => e.id !== env.id)
								.map((e) => (
									<Item
										icon={<ArrowRightIcon />}
										key={e.id}
										keywords={[e.slug, "environment", "switch"]}
										onSelect={() => run(() => router.push(`/${e.slug}`))}
										value={`Switch to ${e.name}`}
									>
										Switch to {e.name}
									</Item>
								))}
						</CommandGroup>
					) : null}
				</CommandList>
				<div className="border-border text-muted-foreground flex items-center gap-4 border-t px-3 py-2 text-xs">
					<span className="flex items-center gap-1.5">
						<ShortcutKeys keys={["↑", "↓"]} /> Navigate
					</span>
					<span className="flex items-center gap-1.5">
						<ShortcutKeys keys={["↵"]} /> Open
					</span>
					<span className="flex items-center gap-1.5">
						<ShortcutKeys keys={["esc"]} /> Close
					</span>
					<span className="ml-auto flex items-center gap-1.5">
						<ShortcutKeys keys={["?"]} /> Shortcuts
					</span>
				</div>
			</Command>
		</CommandDialog>
	);
}
