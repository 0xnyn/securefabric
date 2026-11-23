"use client";

import { create } from "zustand";
import { createFilterSlice } from "@/lib/store/adapters/zustand";
import { field } from "@/lib/store/schema";
import { generateFilterSchema } from "@/lib/table-schema";
import { tableSchema } from "./table-schema";

/** One field per filterable column, plus sort. */
export const filterSchema = generateFilterSchema(tableSchema.definition, {
	sort: field.sort(),
});

export type FilterState = typeof filterSchema._type;

/**
 * Filter state for the connections tab on an integration's page.
 *
 * The connections page keeps its filters in the URL (nuqs), because the
 * sidebar's views are links to filtered lists. An embedded tab can't: the URL
 * already says which tab is open, and filters there would leak between pages.
 * A zustand slice keeps them in memory instead, so they survive switching
 * tabs and coming back, and reset on reload.
 */
export const useEmbeddedFilterStore = create<Record<string, unknown>>(
	(set, get) => ({
		...createFilterSlice(
			filterSchema.definition,
			"integration-connections",
			set,
			get
		),
	})
);
