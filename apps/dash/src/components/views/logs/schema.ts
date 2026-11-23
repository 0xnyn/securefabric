import {
	createNuqsSearchParams,
	type inferParserType,
} from "@/lib/store/adapters/nuqs/server";
import { field } from "@/lib/store/schema";
import { generateFilterSchema } from "@/lib/table-schema";
import { tableSchema } from "./table-schema";

const DIRECTIONS = ["prev", "next"] as const;
export const PAGE_SIZE = 50;

/**
 * Everything the logs table keeps in the URL: one field per filterable
 * column, generated from the table schema, plus the state that isn't a
 * filter: sort, the open row, live mode and the cursor.
 *
 * Because it is the URL, a saved view in the sidebar is just a link
 * (`/logs?level=error`), and so is "see this connection's logs".
 */
export const filterSchema = generateFilterSchema(tableSchema.definition, {
	cursor: field.timestamp(),
	direction: field.stringLiteral(DIRECTIONS).default("next"),
	live: field.boolean(),
	size: field.number().default(PAGE_SIZE),
	sort: field.sort(),
	uuid: field.string(),
});

export type FilterState = typeof filterSchema._type;

export const { searchParamsParser, searchParamsSerializer } =
	createNuqsSearchParams(filterSchema.definition);

export type SearchParams = inferParserType<typeof searchParamsParser>;

/** URL keys that aren't column filters. */
export const STATE_KEYS = new Set([
	"cursor",
	"direction",
	"live",
	"size",
	"sort",
	"uuid",
]);
