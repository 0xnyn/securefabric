import {
	ActivityIcon,
	BlocksIcon,
	BoxesIcon,
	Building2Icon,
	CableIcon,
	ChartColumnIcon,
	DatabaseIcon,
	HouseIcon,
	KeyRoundIcon,
	type LucideIcon,
	PaletteIcon,
	ScrollTextIcon,
	SettingsIcon,
	ShieldAlertIcon,
	ShieldCheckIcon,
	ShieldEllipsisIcon,
	SlidersHorizontalIcon,
	UsersIcon,
	WebhookIcon,
} from "lucide-react";
import type { Access, Requirement } from "@/lib/access";

/** One place in the app. `href` is relative to the environment
 * (`/dev` + href). `shortcut` is the second key of the "G then X" chord.
 * `requires` hides it from people whose role can't use it (lib/access.ts). */
export interface NavItem {
	description: string;
	href: string;
	icon: LucideIcon;
	label: string;
	requires?: Requirement;
	shortcut: string;
}

export interface NavGroup {
	items: NavItem[];
	/** Omitted for the first group, which needs no heading. */
	label?: string;
}

/** The public documentation: guides, connector pages and the API reference. */
export const DOCS_URL = "https://docs.securefabric.dev";

/**
 * The main sidebar, grouped by job: connect tools, read the data they produce,
 * watch it run, then the developer tools. Every page reads the real API
 * (docs/plan/08-dashboard-and-connect-ui.md).
 */
export const NAV_GROUPS: NavGroup[] = [
	{
		items: [
			{
				description: "Sync health, new findings and recent activity",
				href: "",
				icon: HouseIcon,
				label: "Overview",
				shortcut: "O",
			},
		],
	},
	{
		items: [
			{
				description: "Every tool you can connect, and what each one syncs",
				href: "/catalog",
				icon: BoxesIcon,
				label: "Catalog",
				shortcut: "A",
			},
			{
				description: "Tools turned on for this environment",
				href: "/integrations",
				icon: BlocksIcon,
				label: "Integrations",
				requires: { scope: "provisioning:read" },
				shortcut: "I",
			},
			{
				description: "Your customers and the tools they've connected",
				href: "/organizations",
				icon: Building2Icon,
				label: "Organizations",
				requires: { scope: "provisioning:read" },
				shortcut: "G",
			},
			{
				description:
					"Each customer's connected tool, with its health and last sync",
				href: "/connections",
				icon: CableIcon,
				label: "Connections",
				requires: { scope: "provisioning:read" },
				shortcut: "C",
			},
		],
		label: "Connect",
	},
	{
		items: [
			{
				description: "Vulnerabilities found by every connected tool",
				href: "/findings",
				icon: ShieldAlertIcon,
				label: "Findings",
				requires: { scope: "data:read" },
				shortcut: "F",
			},
			{
				description:
					"Repositories, hosts, images and the other things findings affect",
				href: "/resources",
				icon: DatabaseIcon,
				label: "Resources",
				requires: { scope: "data:read" },
				shortcut: "R",
			},
		],
		label: "Data",
	},
	{
		items: [
			{
				description: "What ran, when and how it went, with each request log",
				href: "/logs",
				icon: ScrollTextIcon,
				label: "Logs",
				requires: { scope: "provisioning:read" },
				shortcut: "L",
			},
			{
				description: "API calls, records synced and usage over time",
				href: "/metrics",
				icon: ChartColumnIcon,
				label: "Metrics",
				requires: { scope: "provisioning:read" },
				shortcut: "M",
			},
			{
				description:
					"Endpoints that receive events, and every delivery attempt",
				href: "/webhooks",
				icon: WebhookIcon,
				label: "Webhooks",
				requires: { scope: "webhooks:manage" },
				shortcut: "W",
			},
			{
				description: "Whether SecureFabric and your syncs are running normally",
				href: "/status",
				icon: ActivityIcon,
				label: "Status",
				shortcut: "S",
			},
		],
		label: "Monitor",
	},
	{
		items: [
			{
				description: "Keys your servers use to call the API",
				href: "/keys",
				icon: KeyRoundIcon,
				label: "API keys",
				requires: { scope: "keys:manage" },
				shortcut: "K",
			},
		],
		label: "Developers",
	},
];

export const SETTINGS_ITEM: NavItem = {
	description: "Environment, connect page branding, team and audit log",
	href: "/settings",
	icon: SettingsIcon,
	label: "Settings",
	shortcut: ",",
};

/**
 * The operator console. Not in `NAV_GROUPS` (or `NAV_ITEMS`, which drive the
 * "G then X" shortcuts): the sidebar and the palette show it only when
 * `me.is_operator`, because everyone else gets 403 `operator_required`.
 */
export const OPERATOR_ITEM: Omit<NavItem, "shortcut"> = {
	description: "Alerts, cross-account search, scheduler and repairs",
	href: "/admin",
	icon: ShieldEllipsisIcon,
	label: "Operator console",
};

/** The nav groups this person can use: empty groups drop out. */
export function visibleNavGroups(access: Access): NavGroup[] {
	return NAV_GROUPS.map((g) => ({
		...g,
		items: g.items.filter((i) => access.allows(i.requires)),
	})).filter((g) => g.items.length > 0);
}

export const NAV_ITEMS: NavItem[] = [
	...NAV_GROUPS.flatMap((g) => g.items),
	SETTINGS_ITEM,
];

/** The first path segment after the environment: "" for Overview. */
export function sectionOf(pathname: string): string {
	return pathname.split("/")[2] ?? "";
}

export function isActive(pathname: string, href: string): boolean {
	const section = sectionOf(pathname);
	return href === "" ? section === "" : `/${section}` === href;
}

// ---------------------------------------------------------------------------
// Settings: it takes over the sidebar rather than adding a second one.

export type SettingsSection = "general" | "connect" | "team" | "audit";

export const SETTINGS_SECTIONS: {
	value: SettingsSection;
	label: string;
	icon: LucideIcon;
	description: string;
	requires?: Requirement;
}[] = [
	{
		description:
			"Name this environment and choose where the connect page can redirect people.",
		icon: SlidersHorizontalIcon,
		label: "General",
		value: "general",
	},
	{
		description:
			"Make the connect page your customers see look like your product.",
		icon: PaletteIcon,
		label: "Connect page",
		value: "connect",
	},
	{
		description: "Invite teammates and choose their roles.",
		icon: UsersIcon,
		label: "Team",
		value: "team",
	},
	{
		description: "Who changed what in this environment, and when.",
		icon: ShieldCheckIcon,
		label: "Audit log",
		requires: { admin: true },
		value: "audit",
	},
];

export function settingsSection(value: string | null): SettingsSection {
	return SETTINGS_SECTIONS.find((s) => s.value === value)?.value ?? "general";
}

export interface TabDef<T extends string = string> {
	icon: LucideIcon;
	label: string;
	value: T;
}

export interface Focus {
	kind: "settings";
}

export function focusOf(pathname: string): Focus | null {
	return sectionOf(pathname) === "settings" ? { kind: "settings" } : null;
}
