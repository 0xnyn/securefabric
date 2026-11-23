import { describe, expect, it, vi } from "vitest";
import type { ActionDescriptor, ActionRequest } from "@/lib/actions/types";
import { describeCommand } from "./confirm-dialog";
import {
	ActionRequestError,
	actionsForScope,
	interpolate,
	newCommandId,
	partitionRows,
	postAction,
	rowActionsOf,
	rowScopedActions,
} from "./utils";

const replay: ActionDescriptor = {
	href: "/api/actions/replay",
	id: "replay",
	label: "Replay",
	scope: ["row", "bulk", "filter"],
};
const discard: ActionDescriptor = {
	confirm: "Discard {count} messages?",
	href: "/api/actions/discard",
	id: "discard",
	label: "Discard",
	scope: ["row", "bulk"],
	variant: "destructive",
};
const purge: ActionDescriptor = {
	href: "/api/actions/purge",
	id: "purge",
	label: "Purge",
	scope: ["filter"],
};
const actions = [replay, discard, purge];

describe("interpolate", () => {
	it("replaces known placeholders and leaves unknown ones", () => {
		expect(interpolate("Discard {count} of {total}?", { count: 3 })).toBe(
			"Discard 3 of {total}?"
		);
	});

	it("only reads own properties — prototype names are not variables", () => {
		expect(interpolate("{constructor} {toString}", { count: 1 })).toBe(
			"{constructor} {toString}"
		);
	});

	it("picks a plural form by count", () => {
		expect(interpolate("Delete {count} {log|logs}?", { count: 1 })).toBe(
			"Delete 1 log?"
		);
		expect(interpolate("Delete {count} {log|logs}?", { count: 3 })).toBe(
			"Delete 3 logs?"
		);
	});

	it("does not leak whitespace written around a plural marker", () => {
		expect(interpolate("Delete {count} {log | logs}?", { count: 1 })).toBe(
			"Delete 1 log?"
		);
		expect(interpolate("Delete {count} { log | logs }?", { count: 3 })).toBe(
			"Delete 3 logs?"
		);
	});
});

describe("rowActionsOf", () => {
	it("reads the server stamp and tolerates its absence or garbage", () => {
		expect(rowActionsOf({ _actions: ["a", "b"] })).toEqual(["a", "b"]);
		expect(rowActionsOf({})).toEqual([]);
		expect(rowActionsOf(null)).toEqual([]);
		expect(rowActionsOf({ _actions: "a" })).toEqual([]);
		expect(rowActionsOf({ _actions: ["a", 1, null] })).toEqual(["a"]);
	});
});

describe("scope helpers", () => {
	it("actionsForScope", () => {
		expect(actionsForScope(actions, "bulk").map((a) => a.id)).toEqual([
			"replay",
			"discard",
		]);
		expect(actionsForScope(actions, "filter").map((a) => a.id)).toEqual([
			"replay",
			"purge",
		]);
	});

	it("rowScopedActions is descriptor order ∩ row stamp ∩ row scope", () => {
		expect(
			rowScopedActions(actions, ["purge", "discard", "replay"]).map((a) => a.id)
		).toEqual(["replay", "discard"]);
		expect(rowScopedActions(actions, ["nope"])).toEqual([]);
	});

	it("partitionRows keeps eligible rows and counts the rest", () => {
		const rows = [
			{ original: { _actions: ["replay"], id: 1 } },
			{ original: { _actions: [], id: 2 } },
			{ original: { _actions: ["replay", "discard"], id: 3 } },
		];
		const { eligible, skipped } = partitionRows(rows, "replay", rowActionsOf);
		expect(eligible.map((r) => r.original.id)).toEqual([1, 3]);
		expect(skipped).toBe(1);
		expect(partitionRows([], "replay", rowActionsOf)).toEqual({
			eligible: [],
			skipped: 0,
		});
	});
});

describe("newCommandId", () => {
	it("is unique and prefixed", () => {
		const a = newCommandId();
		const b = newCommandId();
		expect(a).toMatch(/^cmd_/);
		expect(a).not.toBe(b);
	});
});

describe("postAction", () => {
	const request: ActionRequest = {
		cmd_id: "cmd_1",
		ids: ["a"],
		scope: "ids",
	};

	function fetcher(status: number, body: unknown) {
		return vi.fn(
			async () =>
				new Response(body === undefined ? null : JSON.stringify(body), {
					headers: { "content-type": "application/json" },
					status,
				})
		) as unknown as typeof fetch;
	}

	it("POSTs JSON to href and returns applied", async () => {
		const fetch = fetcher(200, { applied: 2 });
		await expect(postAction("/x/replay", request, fetch)).resolves.toEqual({
			applied: 2,
		});
		const [href, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock
			.calls[0] as [string, RequestInit];
		expect(href).toBe("/x/replay");
		expect(init.method).toBe("POST");
		expect(JSON.parse(init.body as string)).toEqual(request);
	});

	it("maps a known error code and carries `actual`", async () => {
		const error = await postAction(
			"/x",
			request,
			fetcher(409, { actual: 7, error: "count_mismatch" })
		).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(ActionRequestError);
		expect(error).toMatchObject({
			actual: 7,
			code: "count_mismatch",
			status: 409,
		});
	});

	it("treats a 2xx without a numeric `applied` as a failure, never as 'applied to 0'", async () => {
		for (const [status, body] of [
			[204, undefined],
			[200, { ok: true }],
			[200, { applied: "2" }],
		] as const) {
			const error = await postAction(
				"/x",
				request,
				fetcher(status, body)
			).catch((e: unknown) => e);
			expect(error).toBeInstanceOf(ActionRequestError);
			expect(error).toMatchObject({ code: "failed", status });
		}
	});

	it("maps an unknown or absent body to `failed`", async () => {
		const e1 = await postAction("/x", request, fetcher(500, undefined)).catch(
			(e: unknown) => e
		);
		expect(e1).toMatchObject({ code: "failed", status: 500 });
		const e2 = await postAction(
			"/x",
			request,
			fetcher(502, { error: "gateway" })
		).catch((e: unknown) => e);
		expect(e2).toMatchObject({ code: "failed", status: 502 });
	});
});

describe("describeCommand", () => {
	it("interpolates the descriptor's confirm copy", () => {
		expect(
			describeCommand({ action: discard, count: 3, scope: "ids", skipped: 0 })
		).toEqual({ description: null, title: "Discard 3 messages?" });
	});

	it("pluralises the descriptor's confirm copy through `{one|other}`", () => {
		const remove = { ...discard, confirm: "Delete {count} {log|logs}?" };
		expect(
			describeCommand({ action: remove, count: 1, scope: "ids", skipped: 0 })
				.title
		).toBe("Delete 1 log?");
		expect(
			describeCommand({ action: remove, count: 2, scope: "ids", skipped: 0 })
				.title
		).toBe("Delete 2 logs?");
	});

	it("falls back to a generic title and pluralises", () => {
		expect(
			describeCommand({ action: replay, count: 1, scope: "ids", skipped: 0 })
				.title
		).toBe("Replay 1 row?");
		expect(
			describeCommand({ action: replay, count: 2, scope: "ids", skipped: 0 })
				.title
		).toBe("Replay 2 rows?");
	});

	it("mentions skipped rows and filter scope", () => {
		expect(
			describeCommand({ action: discard, count: 7, scope: "ids", skipped: 3 })
				.description
		).toBe("3 selected rows don't qualify and will be skipped.");
		expect(
			describeCommand({ action: discard, count: 7, scope: "ids", skipped: 1 })
				.description
		).toBe("1 selected row doesn't qualify and will be skipped.");
		expect(
			describeCommand({
				action: replay,
				count: 40,
				scope: "filter",
				skipped: 0,
			}).description
		).toBe("Applies to every row matching the current filters.");
	});

	it("explains a count mismatch with the server's number", () => {
		expect(
			describeCommand({
				action: replay,
				actual: 38,
				count: 40,
				scope: "filter",
				skipped: 0,
			})
		).toEqual({
			description:
				"The filters matched 40 rows; they now match 38. Apply to 38 rows anyway?",
			title: "Replay: the matching rows changed",
		});
	});
});
