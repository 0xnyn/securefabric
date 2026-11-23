"use client";

import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@securefabric/ui/primitives/dialog";
import { usePathname } from "next/navigation";
import { sectionOf } from "@/lib/nav";
import { SHORTCUT_GROUPS } from "@/lib/shortcuts";
import { useCommandStore } from "./command-store";
import { ShortcutKeys } from "./shortcut-keys";

/**
 * "?": every shortcut that works right now. Groups scoped to a section (the
 * logs table's) only appear on that section, so the list never advertises a
 * key that would do nothing here.
 */
export function ShortcutsDialog() {
	const open = useCommandStore((s) => s.helpOpen);
	const setOpen = useCommandStore((s) => s.setHelpOpen);
	const section = sectionOf(usePathname());
	const groups = SHORTCUT_GROUPS.filter(
		(g) => !g.section || g.section === section
	);
	return (
		<Dialog onOpenChange={setOpen} open={open}>
			<DialogContent className="sm:max-w-2xl">
				<DialogHeader>
					<DialogTitle>Keyboard shortcuts</DialogTitle>
					<DialogDescription>
						Press <ShortcutKeys className="align-middle" id="palette" /> to
						search, or <ShortcutKeys className="align-middle" keys={["?"]} /> to
						open this list from anywhere.
					</DialogDescription>
				</DialogHeader>
				<div className="grid max-h-[60svh] gap-x-8 gap-y-6 overflow-y-auto sm:grid-cols-2">
					{groups.map((group) => (
						<section className="grid content-start gap-1" key={group.label}>
							<h3 className="text-muted-foreground mb-1 text-xs font-medium">
								{group.label}
							</h3>
							{group.shortcuts.map((s) => (
								<div
									className="flex items-center justify-between gap-4 py-1 text-sm"
									key={s.id}
								>
									<span>{s.description}</span>
									<ShortcutKeys id={s.id} />
								</div>
							))}
						</section>
					))}
				</div>
			</DialogContent>
		</Dialog>
	);
}
