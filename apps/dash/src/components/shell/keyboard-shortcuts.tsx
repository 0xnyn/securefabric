"use client";

import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect } from "react";
import { useHref } from "@/components/shell/env-context";
import { NAV_ITEMS } from "@/lib/nav";
import { isTypingTarget, SEQUENCE_TIMEOUT_MS } from "@/lib/shortcuts";
import { useCommandStore } from "./command-store";

/**
 * Focuses whatever counts as "search" on the current page.
 *
 * A page opts in by marking an element: `data-search-trigger` is clicked
 * (the logs table's filter command opens that way), `data-search-input` is
 * focused. With neither, "/" falls back to the palette, so it is never dead.
 */
function focusPageSearch(): void {
	const trigger = document.querySelector<HTMLElement>("[data-search-trigger]");
	if (trigger) {
		trigger.click();
		return;
	}
	const input = document.querySelector<HTMLInputElement>("[data-search-input]");
	if (input) {
		input.focus();
		input.select();
		return;
	}
	useCommandStore.getState().openWith();
}

/** Shortcuts with a modifier work everywhere, even inside a text field. */
function handleModified(event: KeyboardEvent, toggleTheme: () => void): void {
	const key = event.key.toLowerCase();
	if (key === "k" && !event.shiftKey) {
		event.preventDefault();
		const { open, setOpen } = useCommandStore.getState();
		setOpen(!open);
	} else if (key === "l" && event.shiftKey) {
		event.preventDefault();
		toggleTheme();
	}
}

/** Bare keys only count when nothing else wants them. */
function ignoresBareKeys(event: KeyboardEvent): boolean {
	return (
		event.altKey ||
		event.repeat ||
		isTypingTarget(event.target) ||
		useCommandStore.getState().open ||
		useCommandStore.getState().helpOpen
	);
}

/**
 * The app-wide shortcuts in lib/shortcuts.ts. ⌘B is handled by the sidebar
 * provider and the logs table registers its own, so neither is here.
 */
export function KeyboardShortcuts() {
	const router = useRouter();
	const href = useHref();
	const { resolvedTheme, setTheme } = useTheme();

	useEffect(() => {
		let pendingG = false;
		let timer: ReturnType<typeof setTimeout> | undefined;

		const toggleTheme = (): void =>
			setTheme(resolvedTheme === "dark" ? "light" : "dark");

		const finishSequence = (event: KeyboardEvent): void => {
			pendingG = false;
			clearTimeout(timer);
			const key = event.key.toLowerCase();
			const item = NAV_ITEMS.find((n) => n.shortcut.toLowerCase() === key);
			if (item) {
				event.preventDefault();
				router.push(href(item.href));
			}
		};

		const onKeyDown = (event: KeyboardEvent): void => {
			if (event.metaKey || event.ctrlKey) {
				handleModified(event, toggleTheme);
				return;
			}
			if (ignoresBareKeys(event)) {
				return;
			}
			if (pendingG) {
				finishSequence(event);
			} else if (event.key === "/") {
				event.preventDefault();
				focusPageSearch();
			} else if (event.key === "?") {
				event.preventDefault();
				useCommandStore.getState().setHelpOpen(true);
			} else if (event.key === "g") {
				pendingG = true;
				timer = setTimeout(() => {
					pendingG = false;
				}, SEQUENCE_TIMEOUT_MS);
			}
		};

		window.addEventListener("keydown", onKeyDown);
		return () => {
			window.removeEventListener("keydown", onKeyDown);
			clearTimeout(timer);
		};
	}, [router, href, resolvedTheme, setTheme]);

	return null;
}
