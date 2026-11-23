import { type operations, type schemas, unwrap } from "@securefabric/client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "./keys";

export type TaskStatus = schemas["TaskStatus"];
export type TaskState = TaskStatus["state"];
export type Queue = schemas["Queue"];

/** States after which a task never changes again, so polling can stop. */
export const TERMINAL_STATES: ReadonlySet<TaskState> = new Set<TaskState>([
	"completed",
	"failed",
	"cancelled",
]);

const POLL_MS = 1000;

type GetTaskQuery = NonNullable<
	operations["tasks:get_task"]["parameters"]["query"]
>;

/** One durable task's state, polled every second until it settles. */
export const useTask = (taskId: string, queue?: GetTaskQuery["queue"]) =>
	useQuery({
		queryFn: () =>
			unwrap(
				api.GET("/api/v1/tasks/{task_id}", {
					params: { path: { task_id: taskId }, query: { queue } },
				})
			),
		queryKey: queryKeys.tasks.detail(taskId, queue),
		refetchInterval: (query) => {
			const state = query.state.data?.state;
			return state && TERMINAL_STATES.has(state) ? false : POLL_MS;
		},
		retry: false,
	});

export const useCancelTask = () => {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: ({ taskId, queue }: { taskId: string; queue?: Queue }) =>
			unwrap(
				api.POST("/api/v1/tasks/{task_id}/cancel", {
					params: { path: { task_id: taskId }, query: { queue } },
				})
			),
		onSuccess: (_data, { taskId, queue }) =>
			queryClient.invalidateQueries({
				queryKey: queryKeys.tasks.detail(taskId, queue),
			}),
	});
};
