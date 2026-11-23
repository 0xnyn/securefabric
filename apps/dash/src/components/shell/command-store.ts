"use client";

import { create } from "zustand";

/**
 * Which global overlay is open, shared by everything that opens one: the
 * keyboard, the sidebar's search row, empty states that offer "find a
 * connection", and the palette's own "Keyboard shortcuts" item.
 *
 * A store rather than context so the key handler can read the current value
 * without re-subscribing on every change.
 */
interface CommandState {
	/** The "Create environment" dialog, opened from the switcher or ⌘K. */
	createEnvOpen: boolean;
	helpOpen: boolean;
	open: boolean;
	/** Opens the palette, optionally with the search box filled in. */
	openWith: (query?: string) => void;
	query: string;
	setCreateEnvOpen: (open: boolean) => void;
	setHelpOpen: (open: boolean) => void;
	setOpen: (open: boolean) => void;
	setQuery: (query: string) => void;
}

export const useCommandStore = create<CommandState>((set) => ({
	createEnvOpen: false,
	helpOpen: false,
	open: false,
	openWith: (query = "") => set({ helpOpen: false, open: true, query }),
	query: "",
	setCreateEnvOpen: (createEnvOpen) => set({ createEnvOpen, open: false }),
	setHelpOpen: (helpOpen) => set({ helpOpen, open: false }),
	// The query clears on close rather than on open, so reopening doesn't
	// flash the last search before emptying it.
	setOpen: (open) => set(open ? { open } : { open, query: "" }),
	setQuery: (query) => set({ query }),
}));
