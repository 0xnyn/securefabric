import {
	ARRAY_DELIMITER,
	SLIDER_DELIMITER,
	SORT_DELIMITER,
} from "@/lib/delimiters";
import type { FieldBuilder, FieldConfig } from "./types";

// Helper to create a field builder from config
function createFieldBuilder<T>(config: FieldConfig<T>): FieldBuilder<T> {
	const builder: FieldBuilder<T> = {
		get _config() {
			return config;
		},
		default(value: T) {
			return createFieldBuilder({ ...config, defaultValue: value });
		},

		delimiter(separator: string) {
			// Update serialize/parse functions when delimiter changes for arrays
			if (config.type === "array" && config.itemConfig) {
				const itemConfig = config.itemConfig as FieldConfig<unknown>;
				return createFieldBuilder({
					...config,
					delimiter: separator,
					parse: (str: string) => {
						if (!str) {
							return config.defaultValue;
						}
						const items = str.split(separator);
						const parsed = items
							.map((item) => itemConfig.parse(item))
							.filter(
								(item): item is NonNullable<typeof item> => item !== null
							);
						return parsed as T;
					},
					serialize: (value: T) => {
						if (!Array.isArray(value)) {
							return "";
						}
						return value
							.map((item) => itemConfig.serialize(item))
							.join(separator);
					},
				});
			}
			return createFieldBuilder({ ...config, delimiter: separator });
		},

		parse(fn: (value: string) => T | null) {
			return createFieldBuilder({ ...config, parse: fn });
		},

		serialize(fn: (value: T) => string) {
			return createFieldBuilder({ ...config, serialize: fn });
		},
	};

	return builder;
}

// String field
function string(): FieldBuilder<string | null> {
	return createFieldBuilder<string | null>({
		defaultValue: null,
		delimiter: "",
		parse: (str) => (str === "" ? null : str),
		serialize: (value) => (value === null ? "" : String(value)),
		type: "string",
	});
}

// Number field (integer)
function number(): FieldBuilder<number | null> {
	return createFieldBuilder<number | null>({
		defaultValue: null,
		delimiter: "",
		parse: (str) => {
			if (str === "") {
				return null;
			}
			const num = Number.parseInt(str, 10);
			return isNaN(num) ? null : num;
		},
		serialize: (value) => (value === null ? "" : String(value)),
		type: "number",
	});
}

// Boolean field
function boolean(): FieldBuilder<boolean | null> {
	return createFieldBuilder<boolean | null>({
		defaultValue: null,
		delimiter: "",
		parse: (str) => {
			if (str === "") {
				return null;
			}
			if (str === "true") {
				return true;
			}
			if (str === "false") {
				return false;
			}
			return null;
		},
		serialize: (value) => (value === null ? "" : String(value)),
		type: "boolean",
	});
}

// Timestamp field (Date)
function timestamp(): FieldBuilder<Date | null> {
	return createFieldBuilder<Date | null>({
		defaultValue: null,
		delimiter: "",
		parse: (str) => {
			if (str === "") {
				return null;
			}
			const time = Number.parseInt(str, 10);
			if (isNaN(time)) {
				return null;
			}
			const date = new Date(time);
			return isNaN(date.getTime()) ? null : date;
		},
		serialize: (value) => (value === null ? "" : String(value.getTime())),
		type: "timestamp",
	});
}

// String literal field (enum-like)
function stringLiteral<T extends readonly string[]>(
	literals: T
): FieldBuilder<T[number] | null> {
	return createFieldBuilder<T[number] | null>({
		defaultValue: null,
		delimiter: "",
		literals,
		parse: (str) => {
			if (str === "") {
				return null;
			}
			return literals.includes(str as T[number]) ? (str as T[number]) : null;
		},
		serialize: (value) => (value === null ? "" : String(value)),
		type: "stringLiteral",
	});
}

// Array field
function array<T>(itemBuilder: FieldBuilder<T>): FieldBuilder<T[]> {
	const itemConfig = itemBuilder._config;
	const defaultDelimiter =
		itemConfig.type === "number" ? SLIDER_DELIMITER : ARRAY_DELIMITER;

	return createFieldBuilder<T[]>({
		defaultValue: [],
		delimiter: defaultDelimiter,
		itemConfig: itemConfig as FieldConfig<unknown>,
		parse: (str) => {
			if (!str) {
				return [];
			}
			const items = str.split(defaultDelimiter);
			const parsed = items
				.map((item) => itemConfig.parse(item))
				.filter((item): item is T => item !== null);
			return parsed;
		},
		serialize: (value) => {
			if (!Array.isArray(value) || value.length === 0) {
				return "";
			}
			return value
				.map((item) => itemConfig.serialize(item))
				.join(defaultDelimiter);
		},
		type: "array",
	});
}

// Sort field { id: string, desc: boolean }
function sort(): FieldBuilder<{ id: string; desc: boolean } | null> {
	return createFieldBuilder<{ id: string; desc: boolean } | null>({
		defaultValue: null,
		delimiter: SORT_DELIMITER,
		parse: (str) => {
			if (!str) {
				return null;
			}
			const [id, desc] = str.split(SORT_DELIMITER);
			if (!id) {
				return null;
			}
			return { desc: desc === "desc", id };
		},
		serialize: (value) => {
			if (value === null) {
				return "";
			}
			return `${value.id}${SORT_DELIMITER}${value.desc ? "desc" : "asc"}`;
		},
		type: "sort",
	});
}

// Export field builders
export const field = {
	array,
	boolean,
	number,
	sort,
	string,
	stringLiteral,
	timestamp,
};
