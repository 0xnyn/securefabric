import type { schemas } from "@securefabric/client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "./keys";

const HEALTH_POLL_MS = 15_000;

export type Readiness = schemas["Readiness"];

/**
 * The API's readiness probe. A 503 still carries a typed `Readiness` body
 * (the database check failed), so it is returned rather than thrown: only an
 * unreachable API is an error here.
 */
export const useApiReadiness = () =>
	useQuery({
		queryFn: async (): Promise<Readiness> => {
			const { data, error } = await api.GET("/health/ready");
			const body = data ?? error;
			if (!body) {
				throw new Error("The API returned an empty readiness response");
			}
			return body;
		},
		queryKey: queryKeys.health.ready,
		refetchInterval: HEALTH_POLL_MS,
		retry: false,
	});
