"use client";

import { cn } from "@securefabric/ui/lib/utils";
import { Kbd, KbdGroup } from "@securefabric/ui/primitives/kbd";
import { useSyncExternalStore } from "react";
import { type Shortcut, shortcutById } from "@/lib/shortcuts";

const APPLE_PLATFORM = /Mac|iPhone|iPad/u;

function subscribe(): () => void {
	return () => undefined;
}

/** True on macOS and iOS, where "mod" is ⌘. Server render assumes Apple,
 * which is what most of the audience is on, then corrects on hydrate. */
export function useIsApple(): boolean {
	return useSyncExternalStore(
		subscribe,
		() => APPLE_PLATFORM.test(navigator.platform || navigator.userAgent),
		() => true
	);
}

function label(key: string, apple: boolean): string {
	switch (key) {
		case "mod":
			return apple ? "⌘" : "Ctrl";
		case "shift":
			return apple ? "⇧" : "Shift";
		case "alt":
			return apple ? "⌥" : "Alt";
		default:
			return key;
	}
}

/** The keys of a shortcut as keycaps. Pass `id` to look one up in the
 * registry, or `keys` for an ad-hoc hint (↵, esc) in the palette footer. */
export function ShortcutKeys({
	id,
	keys,
	sequence,
	className,
}: {
	id?: string;
	keys?: string[];
	sequence?: boolean;
	className?: string;
}) {
	const apple = useIsApple();
	const shortcut: Shortcut | undefined = id ? shortcutById(id) : undefined;
	const list = shortcut?.keys ?? keys ?? [];
	const isSequence = shortcut?.sequence ?? sequence ?? false;
	if (list.length === 0) {
		return null;
	}
	// A sequence can repeat a key ("G then G"), so a step's position is part of
	// its identity.
	const steps = list.map((key, index) => ({
		id: `${index}:${key}`,
		index,
		key,
	}));
	return (
		<KbdGroup className={cn("shrink-0", className)}>
			{steps.map(({ id: stepId, key, index }) => (
				<span className="inline-flex items-center gap-1" key={stepId}>
					{isSequence && index > 0 ? (
						<span className="text-2xs text-muted-foreground">then</span>
					) : null}
					<Kbd>{label(key, apple)}</Kbd>
				</span>
			))}
		</KbdGroup>
	);
}
