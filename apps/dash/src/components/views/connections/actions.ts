import type {
	ActionDescriptor,
	ActionRequest,
	ActionResponse,
} from "@/lib/actions/types";
import {
	deleteConnection,
	readWorkspace,
	setPaused,
	triggerSync,
} from "@/lib/store";
import type { Connection } from "@/lib/types";

/**
 * Row and bulk actions, in the data-table-actions wire format.
 *
 * Upstream, a server declares these next to their Drizzle handlers and the
 * client renders buttons from the JSON. The playground has no server, so the
 * descriptors are declared here and `connectionActionsFetch` stands in for
 * the POST endpoint, applying each action to the workspace in localStorage.
 * The UI half (row menu, bulk bar, confirmation, toasts) is the block's own.
 */
export function connectionActions(slug: string): ActionDescriptor[] {
	const href = (id: string) => `/${slug}/connections/actions/${id}`;
	return [
		{
			href: href("sync"),
			id: "sync",
			label: "Sync now",
			scope: ["row", "bulk"],
		},
		{
			href: href("pause"),
			id: "pause",
			label: "Pause",
			scope: ["row", "bulk"],
		},
		{
			href: href("resume"),
			id: "resume",
			label: "Resume",
			scope: ["row", "bulk"],
		},
		{
			confirm:
				"Delete {count} {connection|connections}? Their synced records are removed and syncing stops. This can't be undone.",
			href: href("delete"),
			id: "delete",
			label: "Delete",
			scope: ["row", "bulk"],
			variant: "destructive",
		},
	];
}

/** Which actions a connection qualifies for right now: the hint upstream
 * stamps on each row as `_actions`. */
export function rowActionsFor(
	conn: Pick<Connection, "health"> & { paused?: boolean }
): string[] {
	const ids = conn.paused ? ["resume"] : ["sync", "pause"];
	if (conn.health === "SYNCING") {
		return ids.filter((id) => id !== "sync");
	}
	return [...ids, "delete"];
}

const APPLY: Record<string, (slug: string, conn: Connection) => boolean> = {
	delete: (slug, conn) => {
		deleteConnection(slug, conn.id);
		return true;
	},
	pause: (slug, conn) => {
		if (conn.paused) {
			return false;
		}
		setPaused(slug, conn.id, true);
		return true;
	},
	resume: (slug, conn) => {
		if (!conn.paused) {
			return false;
		}
		setPaused(slug, conn.id, false);
		return true;
	},
	sync: (slug, conn) => {
		if (conn.paused || conn.jobs[0]?.status === "RUNNING") {
			return false;
		}
		triggerSync(slug, conn.id);
		return true;
	},
};

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		headers: { "content-type": "application/json" },
		status,
	});
}

/**
 * The action endpoint, in the browser. Like the upstream handler, the
 * request's ids are only a proposal: each is re-checked against the current
 * state (the `when` guard), so a row that changed since it was drawn is
 * skipped, and `applied` can be lower than the number of ids sent.
 */
// Async to match `fetch`; the work itself is synchronous.
export const connectionActionsFetch: typeof fetch = (input, init) =>
	Promise.resolve(applyAction(input, init));

function applyAction(
	input: Parameters<typeof fetch>[0],
	init: Parameters<typeof fetch>[1]
): Response {
	const url = new URL(
		input instanceof Request ? input.url : String(input),
		window.location.origin
	);
	const [, slug = "", , , actionId = ""] = url.pathname.split("/");
	const apply = APPLY[actionId];
	if (!apply) {
		return json({ error: "unknown_action" }, 404);
	}
	const request = JSON.parse(String(init?.body ?? "{}")) as ActionRequest;
	if (request.scope !== "ids") {
		return json({ error: "scope_not_allowed" }, 400);
	}
	const env = readWorkspace()?.environments.find((e) => e.slug === slug);
	if (!env) {
		return json({ error: "invalid_request" }, 400);
	}
	let applied = 0;
	for (const id of request.ids) {
		const conn = env.connections.find((c) => c.id === id);
		if (conn && apply(slug, conn)) {
			applied += 1;
		}
	}
	return json({ applied } satisfies ActionResponse);
}
