"use client";

import { unwrap } from "@securefabric/client";
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
} from "@securefabric/ui/primitives/command";
import { useSidebar } from "@securefabric/ui/primitives/sidebar";
import { useQuery } from "@tanstack/react-query";
import {
	BookOpenIcon,
	Building2Icon,
	CableIcon,
	KeyboardIcon,
	LayersIcon,
	MoonIcon,
	PanelLeftIcon,
	PlusIcon,
	SunIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import type { ReactNode } from "react";
import { useAccess, useEnv, useHref } from "@/components/shell/env-context";
import {
	DOCS_URL,
	NAV_ITEMS,
	OPERATOR_ITEM,
	SETTINGS_SECTIONS,
} from "@/lib/nav";
import { useCommandStore } from "./command-store";
import { ShortcutKeys } from "./shortcut-keys";

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

/** ⌘K: commands, places, and connections and organizations by name (live from the API). */
export function CommandPalette() {
	const { open, setOpen, query, setQuery, setHelpOpen, setCreateEnvOpen } =
		useCommandStore();
	const router = useRouter();
	const href = useHref();
	const { env, client, me } = useEnv();
	const access = useAccess();
	const { resolvedTheme, setTheme } = useTheme();
	const { toggleSidebar } = useSidebar();
	const connections = useQuery({
		enabled: open,
		queryFn: () =>
			unwrap(
				client.GET("/v1/connections", { params: { query: { limit: 100 } } })
			),
		queryKey: ["palette", env.id, "connections"],
	});
	const orgs = useQuery({
		enabled: open,
		queryFn: () =>
			unwrap(
				client.GET("/v1/organizations", { params: { query: { limit: 100 } } })
			),
		queryKey: ["palette", env.id, "organizations"],
	});
	const orgName = new Map((orgs.data?.items ?? []).map((o) => [o.id, o.name]));
	const run = (fn: () => void): void => {
		setOpen(false);
		fn();
	};
	const go = (path: string): void => run(() => router.push(href(path)));
	return (
		<CommandDialog
			className="sm:max-w-xl"
			description="Search pages, connections, organizations and commands"
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
					<CommandGroup heading="Commands">
						{access.can("provisioning:write") ? (
							<>
								<Item
									icon={<PlusIcon />}
									keywords={["new", "create", "connect", "sandbox"]}
									onSelect={() => go("/connections?new=1")}
									value="Add connection"
								>
									Add connection
								</Item>
								<Item
									icon={<Building2Icon />}
									keywords={["new", "customer"]}
									onSelect={() => go("/organizations?new=1")}
									value="Add organization"
								>
									Add organization
								</Item>
							</>
						) : null}
						{access.isAdmin ? (
							<Item
								icon={<LayersIcon />}
								keywords={["new", "staging", "production"]}
								onSelect={() => run(() => setCreateEnvOpen(true))}
								value="Create environment"
							>
								Create environment
							</Item>
						) : null}
						<Item
							icon={<BookOpenIcon />}
							keywords={["docs", "api", "reference", "help", "guide"]}
							onSelect={() =>
								run(() => window.open(DOCS_URL, "_blank", "noopener"))
							}
							value="Open docs and API reference"
						>
							Open docs and API reference
						</Item>
						<Item
							icon={resolvedTheme === "dark" ? <SunIcon /> : <MoonIcon />}
							keywords={["theme", "dark", "light"]}
							onSelect={() =>
								run(() => setTheme(resolvedTheme === "dark" ? "light" : "dark"))
							}
							value="Toggle theme"
						>
							Toggle theme
						</Item>
						<Item
							icon={<PanelLeftIcon />}
							onSelect={() => run(toggleSidebar)}
							value="Toggle sidebar"
						>
							Toggle sidebar
						</Item>
						<Item
							icon={<KeyboardIcon />}
							onSelect={() => run(() => setHelpOpen(true))}
							value="Keyboard shortcuts"
						>
							Keyboard shortcuts
						</Item>
					</CommandGroup>
					<CommandSeparator />
					<CommandGroup heading="Go to">
						{NAV_ITEMS.filter((n) => access.allows(n.requires)).map((n) => (
							<Item
								icon={<n.icon />}
								key={n.href}
								keywords={[n.description]}
								onSelect={() => go(n.href)}
								value={n.label}
							>
								{n.label}
							</Item>
						))}
						{me.is_operator ? (
							<Item
								icon={<OPERATOR_ITEM.icon />}
								keywords={["admin", "operator", OPERATOR_ITEM.description]}
								onSelect={() => go(OPERATOR_ITEM.href)}
								value={OPERATOR_ITEM.label}
							>
								{OPERATOR_ITEM.label}
							</Item>
						) : null}
						{SETTINGS_SECTIONS.filter((s) => access.allows(s.requires)).map(
							(s) => (
								<Item
									icon={<s.icon />}
									key={s.value}
									keywords={["settings", s.description]}
									onSelect={() => go(`/settings?tab=${s.value}`)}
									value={`Settings: ${s.label}`}
								>
									Settings: {s.label}
								</Item>
							)
						)}
					</CommandGroup>
					{(connections.data?.items.length ?? 0) > 0 ? (
						<CommandGroup heading="Connections">
							{connections.data?.items.map((c) => (
								<Item
									hint={c.vendor}
									icon={<CableIcon />}
									key={c.id}
									keywords={[c.id, c.identifier ?? "", c.vendor]}
									onSelect={() => go(`/connections/${c.id}`)}
									value={`${orgName.get(c.organization_id) ?? "Connection"} ${c.identifier ?? c.id}`}
								>
									{orgName.get(c.organization_id) ?? c.identifier ?? c.id}
								</Item>
							))}
						</CommandGroup>
					) : null}
					{(orgs.data?.items.length ?? 0) > 0 ? (
						<CommandGroup heading="Organizations">
							{orgs.data?.items.map((o) => (
								<Item
									hint={o.identifier}
									icon={<Building2Icon />}
									key={o.id}
									keywords={[o.id, o.identifier]}
									onSelect={() => go(`/organizations/${o.id}`)}
									value={`${o.name} ${o.identifier}`}
								>
									{o.name}
								</Item>
							))}
						</CommandGroup>
					) : null}
				</CommandList>
			</Command>
		</CommandDialog>
	);
}
