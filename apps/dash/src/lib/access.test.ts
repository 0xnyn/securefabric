import { describe, expect, it } from "vitest";
import { accessFor, deniedReason } from "./access";
import { NAV_GROUPS, visibleNavGroups } from "./nav";

// Mirrors tenancy.ROLE_SCOPES in packages/domain: the dashboard must hide
// exactly what the API would refuse.
const ALL = [
	"provisioning:read",
	"provisioning:write",
	"data:read",
	"jobs:execute",
	"webhooks:manage",
	"keys:manage",
	"actions:write",
];
const person = (role: string, scopes: string[]) => ({
	kind: "user",
	role,
	scopes,
});
const admin = accessFor(person("admin", ALL));
const developer = accessFor(
	person(
		"developer",
		ALL.filter((s) => s !== "keys:manage")
	)
);
const support = accessFor(
	person("support", ["provisioning:read", "data:read"])
);

function navHrefs(access: ReturnType<typeof accessFor>): string[] {
	return visibleNavGroups(access).flatMap((g) => g.items.map((i) => i.href));
}

describe("roles", () => {
	it("admins see every page", () => {
		expect(navHrefs(admin)).toEqual(
			NAV_GROUPS.flatMap((g) => g.items.map((i) => i.href))
		);
		expect(admin.allows({ admin: true })).toBe(true);
	});

	it("developers lose API keys and admin-only settings", () => {
		expect(navHrefs(developer)).not.toContain("/keys");
		expect(navHrefs(developer)).toContain("/webhooks");
		expect(developer.allows({ admin: true })).toBe(false);
		expect(developer.readOnly).toBe(false);
	});

	it("support is read-only and has no webhooks or keys", () => {
		const hrefs = navHrefs(support);
		expect(hrefs).not.toContain("/webhooks");
		expect(hrefs).not.toContain("/keys");
		expect(hrefs).toContain("/findings");
		expect(hrefs).toContain("/status");
		expect(support.readOnly).toBe(true);
		expect(support.allows({ scope: "provisioning:write" })).toBe(false);
	});

	it("an API key counts as an admin but keeps its own scopes", () => {
		const key = accessFor({
			kind: "api_key",
			role: null,
			scopes: ["data:read"],
		});
		expect(key.isAdmin).toBe(true);
		expect(key.allows({ admin: true })).toBe(true);
		expect(key.allows({ scope: "keys:manage" })).toBe(false);
		expect(
			deniedReason({ scope: "keys:manage" }, key).startsWith(
				"This API key doesn't include this"
			)
		).toBe(true);
	});

	it("explains a missing admin role by name", () => {
		expect(deniedReason({ admin: true }, developer)).toBe(
			"Only admins can do this. Ask an admin on your team to change your Developer role."
		);
	});
});
