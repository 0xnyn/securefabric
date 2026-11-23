import type { schemas } from "@securefabric/client";
import { unwrap } from "@securefabric/client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "./keys";

const STATUS_POLL_MS = 5000;

export type SystemStatus = schemas["SystemStatus"];
export type StatusLevel = SystemStatus["status"];

/** `GET /api/v1/status`: the same facts `make status` prints. */
export const useSystemStatus = () =>
	useQuery({
		queryFn: () => unwrap(api.GET("/api/v1/status")),
		queryKey: queryKeys.status,
		refetchInterval: STATUS_POLL_MS,
		retry: false,
	});
