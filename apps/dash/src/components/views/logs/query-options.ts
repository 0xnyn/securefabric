import { createDataTableQueryOptions } from "@/lib/data-table";
import { logsFetch } from "./endpoint";
import { type SearchParams, searchParamsSerializer } from "./schema";
import type { LogRow } from "./table-schema";

/** Query options for one environment's logs. The endpoint is per-env, so
 * switching environments is a different cache entry, not a refetch. */
export function logsQueryOptions(slug: string) {
	const options = createDataTableQueryOptions<
		LogRow[],
		Record<string, unknown>
	>({
		apiEndpoint: `/${slug}/logs/api`,
		queryKeyPrefix: `logs:${slug}`,
		// The store is local, so nothing goes stale behind the user's back
		// except new operations, which live mode and refresh pick up.
		queryOptions: { staleTime: 0 },
		searchParamsSerializer: searchParamsSerializer as (
			search: Record<string, unknown>
		) => string,
		skipMetaOnPagination: true,
		transport: { fetch: logsFetch },
	});
	return (search: SearchParams) =>
		options(search as unknown as Record<string, unknown>);
}
