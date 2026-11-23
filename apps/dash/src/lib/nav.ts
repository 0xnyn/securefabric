import {
	ActivityIcon,
	BellIcon,
	BlocksIcon,
	BoxesIcon,
	BracesIcon,
	BugIcon,
	CableIcon,
	ChartColumnIcon,
	ClipboardCheckIcon,
	CloudIcon,
	CodeIcon,
	ContainerIcon,
	DatabaseIcon,
	FingerprintIcon,
	HandshakeIcon,
	HouseIcon,
	KeyRoundIcon,
	LaptopIcon,
	LayoutDashboardIcon,
	type LucideIcon,
	MailIcon,
	NetworkIcon,
	PackageIcon,
	PaletteIcon,
	RadarIcon,
	RefreshCwIcon,
	ScrollTextIcon,
	Settings2Icon,
	SettingsIcon,
	ShieldAlertIcon,
	SlidersHorizontalIcon,
	SmartphoneIcon,
	TerminalIcon,
	TicketIcon,
	UsersIcon,
	VariableIcon,
	WebhookIcon,
	WorkflowIcon,
} from "lucide-react";
import type { CategoryKey } from "./catalog";

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
 * The main sidebar. These never move and never change with the page, so
 * they can be learned. Places with their own sections (Settings, the
 * catalog, a connection) take the whole sidebar over instead of adding a
 * second list under this one; see `focusOf` below.
 *
 * Grouped by job rather than alphabetically: building the integration,
 * watching it run, then the developer tools (the playground and keys).
 */
export const NAV_GROUPS: NavGroup[] = [
	{
		items: [
			{
				description: "Health, traffic and what needs attention",
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
				description: "Every security tool SecureFabric connects to",
				href: "/catalog",
				icon: BoxesIcon,
				label: "Catalog",
				shortcut: "A",
			},
			{
				description: "Tools enabled in this environment",
				href: "/integrations",
				icon: BlocksIcon,
				label: "Integrations",
				shortcut: "I",
			},
			{
				description: "Customer accounts connected to your integrations",
				href: "/connections",
				icon: CableIcon,
				label: "Connections",
				shortcut: "C",
			},
		],
		label: "Build",
	},
	{
		items: [
			{
				description: "Auth events, syncs, API calls and webhooks",
				href: "/logs",
				icon: ScrollTextIcon,
				label: "Logs",
				shortcut: "L",
			},
			{
				description: "API traffic, sync throughput and health",
				href: "/metrics",
				icon: ChartColumnIcon,
				label: "Metrics",
				shortcut: "M",
			},
		],
		label: "Observe",
	},
	{
		items: [
			{
				description: "API, database, worker and queue health",
				href: "/status",
				icon: ActivityIcon,
				label: "Status",
				shortcut: "S",
			},
			{
				description: "Spawn durable workflows on the SecureFabric API",
				href: "/workflows",
				icon: WorkflowIcon,
				label: "Workflows",
				shortcut: "W",
			},
			{
				description: "Send requests against sandbox data",
				href: "/playground",
				icon: TerminalIcon,
				label: "Playground",
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
	description: "Keys, webhooks, Connect UI and team",
	href: "/settings",
	icon: SettingsIcon,
	label: "Settings",
	shortcut: ",",
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

export type SettingsSection =
	| "general"
	| "webhooks"
	| "connect"
	| "variables"
	| "team";

export const SETTINGS_SECTIONS: {
	value: SettingsSection;
	label: string;
	icon: LucideIcon;
	description: string;
}[] = [
	{
		description: "Name, callback URL, danger zone",
		icon: SlidersHorizontalIcon,
		label: "General",
		value: "general",
	},
	{
		description: "Endpoints, events and signing secret",
		icon: WebhookIcon,
		label: "Webhooks",
		value: "webhooks",
	},
	{
		description: "Branding for the hosted connect flow",
		icon: PaletteIcon,
		label: "Connect UI",
		value: "connect",
	},
	{
		description: "Values your integrations can read",
		icon: VariableIcon,
		label: "Environment variables",
		value: "variables",
	},
	{
		description: "Members and roles",
		icon: UsersIcon,
		label: "Team",
		value: "team",
	},
];

export function settingsSection(value: string | null): SettingsSection {
	return SETTINGS_SECTIONS.find((s) => s.value === value)?.value ?? "general";
}

// ---------------------------------------------------------------------------
// Detail-page tabs. They live in the URL (?tab=) so the focused sidebar can
// list them and a link can open one directly.

export interface TabDef<T extends string = string> {
	icon: LucideIcon;
	label: string;
	value: T;
}

export const CONNECTION_TABS = [
	{ icon: LayoutDashboardIcon, label: "Overview", value: "overview" },
	{ icon: DatabaseIcon, label: "Records", value: "records" },
	{ icon: RefreshCwIcon, label: "Sync jobs", value: "jobs" },
	{ icon: KeyRoundIcon, label: "Authorization", value: "auth" },
	{ icon: ScrollTextIcon, label: "Logs", value: "logs" },
	{ icon: SlidersHorizontalIcon, label: "Settings", value: "settings" },
] as const satisfies readonly TabDef[];

export type ConnectionTab = (typeof CONNECTION_TABS)[number]["value"];

export const INTEGRATION_TABS = [
	{ icon: CableIcon, label: "Connections", value: "connections" },
	{ icon: Settings2Icon, label: "Configuration", value: "configuration" },
	{ icon: SlidersHorizontalIcon, label: "Settings", value: "settings" },
] as const satisfies readonly TabDef[];

export type IntegrationTab = (typeof INTEGRATION_TABS)[number]["value"];

export const PROVIDER_TABS = [
	{ icon: LayoutDashboardIcon, label: "Overview", value: "overview" },
	{ icon: KeyRoundIcon, label: "Authentication", value: "auth" },
	{ icon: DatabaseIcon, label: "Sample data", value: "data" },
	{ icon: BracesIcon, label: "API", value: "api" },
] as const satisfies readonly TabDef[];

export type ProviderTab = (typeof PROVIDER_TABS)[number]["value"];

/** A tool that isn't available yet has nothing to authenticate or query. */
export function providerTabs(
	status: "ga" | "beta" | "soon"
): readonly TabDef<ProviderTab>[] {
	return status === "soon" ? PROVIDER_TABS.slice(0, 1) : PROVIDER_TABS;
}

// ---------------------------------------------------------------------------
// Catalog: categories by job, each with an icon so the sidebar still lists
// them when it collapses to icons.

export const CATEGORY_ICONS: Record<CategoryKey, LucideIcon> = {
	appsec: CodeIcon,
	asset: PackageIcon,
	"bug-bounty": BugIcon,
	cloud: CloudIcon,
	container: ContainerIcon,
	data: DatabaseIcon,
	email: MailIcon,
	endpoint: LaptopIcon,
	grc: ClipboardCheckIcon,
	identity: FingerprintIcon,
	mdm: SmartphoneIcon,
	network: NetworkIcon,
	notifications: BellIcon,
	siem: ScrollTextIcon,
	"threat-intel": RadarIcon,
	ticketing: TicketIcon,
	tprm: HandshakeIcon,
	vulnerability: ShieldAlertIcon,
};

export const CATEGORY_GROUPS: { label: string; categories: CategoryKey[] }[] = [
	{
		categories: ["vulnerability", "appsec", "cloud", "container", "bug-bounty"],
		label: "Find risk",
	},
	{
		categories: ["endpoint", "siem", "threat-intel", "email", "network"],
		label: "Detect and respond",
	},
	{
		categories: ["identity", "mdm", "asset", "data"],
		label: "Identity and assets",
	},
	{
		categories: ["grc", "tprm", "ticketing", "notifications"],
		label: "Govern and operate",
	},
];

// ---------------------------------------------------------------------------
// Focus: places that take the sidebar over, the way Settings does, instead
// of stacking their own list under the main nav.

export type Focus =
	| { kind: "settings" }
	| { kind: "catalog" }
	| { kind: "playground" }
	| { kind: "provider"; id: string };

export function focusOf(pathname: string): Focus | null {
	const parts = pathname.split("/");
	const section = parts.at(2) ?? "";
	const raw = parts.at(3);
	const id = raw ? decodeURIComponent(raw) : undefined;
	switch (section) {
		case "settings":
			return { kind: "settings" };
		case "playground":
			return { kind: "playground" };
		case "catalog":
			return id ? { id, kind: "provider" } : { kind: "catalog" };
		default:
			return null;
	}
}
