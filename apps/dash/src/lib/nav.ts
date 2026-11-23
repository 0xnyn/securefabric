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
	TerminalIcon,
	UsersIcon,
	WebhookIcon,
} from "lucide-react";

/** One place in the app. `href` is relative to the environment
 * (`/dev` + href). `shortcut` is the second key of the "G then X" chord. */
export interface NavItem {
	description: string;
	href: string;
	icon: LucideIcon;
	label: string;
	shortcut: string;
}

export interface NavGroup {
	items: NavItem[];
	/** Omitted for the first group, which needs no heading. */
	label?: string;
}

/**
 * The main sidebar, grouped by job: connect tools, read the data they produce,
 * watch it run, then the developer tools. Every page reads the real API
 * (docs/plan/08-dashboard-and-connect-ui.md).
 */
export const NAV_GROUPS: NavGroup[] = [
	{
		items: [
			{
				description: "Health, freshness, findings and recent jobs",
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
				description: "Every connector, from its manifest",
				href: "/catalog",
				icon: BoxesIcon,
				label: "Catalog",
				shortcut: "A",
			},
			{
				description: "Connectors enabled in this environment",
				href: "/integrations",
				icon: BlocksIcon,
				label: "Integrations",
				shortcut: "I",
			},
			{
				description: "Your customers and their connections",
				href: "/organizations",
				icon: Building2Icon,
				label: "Organizations",
				shortcut: "G",
			},
			{
				description: "Vendor tenants, their health and sync status",
				href: "/connections",
				icon: CableIcon,
				label: "Connections",
				shortcut: "C",
			},
		],
		label: "Connect",
	},
	{
		items: [
			{
				description: "Vulnerability findings across connections",
				href: "/findings",
				icon: ShieldAlertIcon,
				label: "Findings",
				shortcut: "F",
			},
			{
				description: "Repositories, hosts, images and more",
				href: "/resources",
				icon: DatabaseIcon,
				label: "Resources",
				shortcut: "R",
			},
		],
		label: "Data",
	},
	{
		items: [
			{
				description: "Syncs, verifications, webhooks and actions",
				href: "/logs",
				icon: ScrollTextIcon,
				label: "Logs",
				shortcut: "L",
			},
			{
				description: "API calls, sync volume and usage",
				href: "/metrics",
				icon: ChartColumnIcon,
				label: "Metrics",
				shortcut: "M",
			},
			{
				description: "Endpoints, deliveries and replay",
				href: "/webhooks",
				icon: WebhookIcon,
				label: "Webhooks",
				shortcut: "W",
			},
		],
		label: "Observe",
	},
	{
		items: [
			{
				description: "API, database, workers and queues",
				href: "/status",
				icon: ActivityIcon,
				label: "Status",
				shortcut: "S",
			},
			{
				description: "Send any API request with your credentials",
				href: "/playground",
				icon: TerminalIcon,
				label: "Request console",
				shortcut: "P",
			},
			{
				description: "API keys and their scopes",
				href: "/keys",
				icon: KeyRoundIcon,
				label: "Keys",
				shortcut: "K",
			},
		],
		label: "Developers",
	},
];

export const SETTINGS_ITEM: NavItem = {
	description: "Environment, connect UI and team",
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
}[] = [
	{
		description: "Name and allowed redirect origins",
		icon: SlidersHorizontalIcon,
		label: "General",
		value: "general",
	},
	{
		description: "Branding for the hosted connect flow",
		icon: PaletteIcon,
		label: "Connect UI",
		value: "connect",
	},
	{
		description: "Members and roles",
		icon: UsersIcon,
		label: "Team",
		value: "team",
	},
	{
		description: "Who did what in this environment",
		icon: ShieldCheckIcon,
		label: "Audit log",
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
