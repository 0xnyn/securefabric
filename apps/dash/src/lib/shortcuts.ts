import { NAV_ITEMS } from "./nav";

/**
 * Every keyboard shortcut in the playground, in one list.
 *
 * The global handler, the ⌘K palette (which prints them beside its items) and
 * the "?" help sheet all read from here, so a shortcut can't exist without
 * being discoverable, and the help can't advertise one that doesn't work.
 *
 * `keys` is what the user presses, one entry per key, in order. "mod" renders
 * as ⌘ on Apple platforms and Ctrl elsewhere. A chord ("G then L") is written
 * as two entries marked `sequence: true`.
 */
export interface Shortcut {
	description: string;
	id: string;
	keys: string[];
	/** True for sequences (press one, then the other) rather than combos. */
	sequence?: boolean;
}

export interface ShortcutGroup {
	label: string;
	/** Only shown in the help sheet while this section is open. */
	section?: string;
	shortcuts: Shortcut[];
}

export const SHORTCUT_GROUPS: ShortcutGroup[] = [
	{
		label: "General",
		shortcuts: [
			{
				description: "Search and run commands",
				id: "palette",
				keys: ["mod", "K"],
			},
			{
				description: "Toggle the sidebar",
				id: "sidebar",
				keys: ["mod", "B"],
			},
			{
				description: "Search or filter this page",
				id: "search",
				keys: ["/"],
			},
			{
				description: "Show keyboard shortcuts",
				id: "help",
				keys: ["?"],
			},
			{
				description: "Toggle light and dark theme",
				id: "theme",
				keys: ["mod", "shift", "L"],
			},
		],
	},
	{
		label: "Go to",
		shortcuts: NAV_ITEMS.map((item) => ({
			description: item.label,
			id: `go:${item.href || "/"}`,
			keys: ["G", item.shortcut],
			sequence: true,
		})),
	},
	{
		label: "Logs table",
		section: "logs",
		shortcuts: [
			{
				description: "Toggle the filter rail",
				id: "logs:filters",
				keys: ["mod", "shift", "B"],
			},
			{
				description: "Reset all filters",
				id: "logs:reset",
				keys: ["mod", "Esc"],
			},
			{
				description: "Reset column order and visibility",
				id: "logs:columns",
				keys: ["mod", "U"],
			},
			{
				description: "Clear the selected rows",
				id: "logs:clear-selection",
				keys: ["mod", "shift", "X"],
			},
			{
				description: "Previous and next row in the detail sheet",
				id: "logs:step",
				keys: ["↑", "↓"],
			},
			{
				description: "Toggle live mode",
				id: "logs:live",
				keys: ["mod", "J"],
			},
		],
	},
];

export const SHORTCUTS: Shortcut[] = SHORTCUT_GROUPS.flatMap(
	(g) => g.shortcuts
);

export function shortcutById(id: string): Shortcut | undefined {
	return SHORTCUTS.find((s) => s.id === id);
}

/** How long the second key of a "G then X" chord is waited for. */
export const SEQUENCE_TIMEOUT_MS = 1200;

/** Whether keystrokes belong to a text field rather than to the app. */
export function isTypingTarget(target: EventTarget | null): boolean {
	if (!(target instanceof HTMLElement)) {
		return false;
	}
	return (
		target.isContentEditable ||
		target.tagName === "INPUT" ||
		target.tagName === "TEXTAREA" ||
		target.tagName === "SELECT"
	);
}
