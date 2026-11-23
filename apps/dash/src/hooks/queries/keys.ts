/**
 * Query keys, one factory per resource, so invalidation can target a whole
 * resource (`queryKeys.tasks.all`) or one entry (`queryKeys.tasks.detail(id)`).
 */
export const queryKeys = {
	health: {
		ready: ["health", "ready"] as const,
	},
	status: ["status"] as const,
	tasks: {
		all: ["tasks"] as const,
		detail: (taskId: string, queue?: string) =>
			["tasks", taskId, { queue }] as const,
	},
};
