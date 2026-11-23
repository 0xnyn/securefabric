import { describe, expect, it } from "vitest";
import { ENDPOINTS, simulate } from "./endpoints";
import { fixtureEnvironment } from "./test-fixtures";

const NOW = Date.UTC(2026, 10, 1);

function setup(id: string) {
	const env = fixtureEnvironment(NOW);
	const ep = ENDPOINTS.find((e) => e.id === id);
	if (!(env && ep)) {
		throw new Error(`Missing environment or endpoint ${id}`);
	}
	const conn = env.connections.find((c) => c.counts.vulnerabilities) ?? null;
	return { conn, env, ep };
}

function listBody(params: Record<string, string>) {
	const { conn, env, ep } = setup("list-vulnerabilities");
	const res = simulate(env, ep, conn, params, {});
	expect(res.status).toBe(200);
	return res.body as Record<string, unknown> & { items: { id: string }[] };
}

describe("list paging (Leen v1)", () => {
	it("returns offset pages with count and total by default", () => {
		const body = listBody({ limit: "10" });
		expect(Object.keys(body).sort()).toEqual(["count", "items", "total"]);
		expect(body.count).toBe(10);
		expect(body.items).toHaveLength(10);
		expect(body.total).toBeGreaterThan(10);
	});

	it("skips records with offset", () => {
		const first = listBody({ limit: "10" });
		const second = listBody({ limit: "5", offset: "5" });
		expect(second.items[0]?.id).toBe(first.items[5]?.id);
	});

	it("returns cursor pages when enableCursor is true", () => {
		const page = listBody({ enableCursor: "true", limit: "10" });
		expect(Object.keys(page).sort()).toEqual([
			"items",
			"next_cursor",
			"previous_cursor",
		]);
		expect(page.previous_cursor).toBeNull();
		const next = listBody({
			cursor: String(page.next_cursor),
			enableCursor: "true",
			limit: "10",
		});
		expect(next.items[0]?.id).not.toBe(page.items[0]?.id);
		expect(next.previous_cursor).not.toBeNull();
	});

	it("lists connections in the offset envelope", () => {
		const { env, ep } = setup("list-connections");
		const body = simulate(env, ep, null, {}, {}).body as Record<
			string,
			unknown
		>;
		expect(body.count).toBe(env.connections.length);
		expect(body.total).toBe(env.connections.length);
	});
});
