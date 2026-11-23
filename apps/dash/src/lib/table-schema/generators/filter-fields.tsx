import type { JSX } from "react";
import { DataTableCellLevelIndicator } from "@/components/data-table/data-table-cell/data-table-cell-level-indicator";
import type {
	CheckboxOptionProps,
	DataTableFilterField,
	Option,
} from "@/components/data-table/types";
import { fromPresetDescriptor, resolveColumns } from "../col";
import type { ResolvedColumn, TableSchemaDefinition } from "../types";

/**
 * The checkbox option a display picks when the column supplied no
 * `component` of its own. A `level-indicator` column shows the same dot it
 * renders in its cells (after the label, clear of the checkbox), so the
 * filter sidebar reads like the table — which
 * is why it is limited to the kinds whose cells draw the dot (`renderCell`
 * falls back to plain text for anything but a string).
 */
function defaultFilterComponent(
	config: ResolvedColumn,
	options?: Option[]
): ((props: CheckboxOptionProps) => JSX.Element | null) | undefined {
	if (config.display.type !== "level-indicator") {
		return undefined;
	}
	if (config.kind !== "enum" && config.kind !== "string") {
		return undefined;
	}
	const colorMap = config.display.colorMap;
	// The dot follows the label, so every option is sized to the widest label
	// to keep the dots in one column. The filter passes the field's options,
	// which win over the schema's: a field filled from facets after this
	// component was created only has them there.
	return function LevelOption({
		label,
		value,
		options: rendered = options,
	}: CheckboxOptionProps) {
		return (
			<DataTableCellLevelIndicator
				alignLabels={widestLabelCandidates(rendered)}
				color={colorMap?.[String(value)]}
				dotPosition="end"
				label={label}
				showLabel
				value={String(value)}
			/>
		);
	};
}

/** Each option renders a sizer per label, so a long list is cut to a few. */
const MAX_ALIGN_LABELS = 8;

// Every option of a filter asks for the same list on every render, so the
// shortlist is kept per options array — a large facet is sorted once, not once
// per row.
const candidatesCache = new WeakMap<Option[], string[]>();

/**
 * The labels that might be the widest. Character count only shortlists them —
 * the browser does the measuring — so a miss costs alignment, never text.
 */
export function widestLabelCandidates(options?: Option[]): string[] {
	if (!options) {
		return [];
	}
	const cached = candidatesCache.get(options);
	if (cached) {
		return cached;
	}
	const candidates = [...new Set(options.map((o) => o.label))]
		.sort((a, b) => b.length - a.length)
		.slice(0, MAX_ALIGN_LABELS);
	candidatesCache.set(options, candidates);
	return candidates;
}

/**
 * Generate DataTableFilterField[] from a table schema definition.
 *
 * Only includes fields where filter !== null.
 * Order follows schema definition order (JS object key insertion order).
 *
 * Options for checkbox fields are auto-derived from col.enum(values) or
 * col.boolean() if not explicitly provided via filterable("checkbox", { options }).
 */
export function generateFilterFields<TData>(
	schema: TableSchemaDefinition
): DataTableFilterField<TData>[] {
	const result: DataTableFilterField<TData>[] = [];

	for (const config of resolveColumns(schema)) {
		const { key, filter, label, kind } = config;
		if (!filter) {
			continue;
		}

		const base = {
			commandDisabled: filter.commandDisabled || undefined,
			defaultOpen: filter.defaultOpen || undefined,
			label,
			value: key as keyof TData,
		};

		switch (filter.type) {
			case "input": {
				result.push({ ...base, type: "input" });
				break;
			}
			case "timerange": {
				result.push({
					...base,
					presets: filter.presets?.map(fromPresetDescriptor),
					type: "timerange",
				});
				break;
			}
			case "checkbox": {
				// Derive options if not explicitly provided
				let options = filter.options;
				if (!options) {
					if (config.kind === "enum") {
						options = config.enumValues.map((v) => ({ label: v, value: v }));
					} else if (kind === "boolean") {
						options = [
							{ label: "Yes", value: true },
							{ label: "No", value: false },
						];
					} else if (
						config.kind === "array" &&
						config.arrayItem.kind === "enum"
					) {
						options = config.arrayItem.enumValues.map((v) => ({
							label: v,
							value: v,
						}));
					}
				}
				result.push({
					...base,
					component:
						config.renderers.filterComponent ??
						defaultFilterComponent(config, options),
					options,
					type: "checkbox",
				});
				break;
			}
			case "slider": {
				const displayUnit =
					"unit" in config.display ? config.display.unit : undefined;
				result.push({
					...base,
					max: filter.max ?? 100,
					min: filter.min ?? 0,
					type: "slider",
					unit: filter.unit ?? displayUnit,
				});
				break;
			}
		}
	}

	return result;
}
