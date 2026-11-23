import { describe, expect, it } from "vitest";
import { generateRecords } from "./records";
import { toWire } from "./wire";

const NOW = Date.UTC(2026, 10, 1);

function first(provider: string, model: Parameters<typeof toWire>[0]) {
	const [record] = generateRecords(
		"conn_test",
		provider,
		model,
		"acme.com",
		NOW,
		5
	);
	if (!record) {
		throw new Error(`No ${model} records for ${provider}`);
	}
	return toWire(model, record);
}

const SNAKE = /^[a-z0-9_]+$/u;
const VERDICT = /^[A-Z_]+$/u;

describe("toWire", () => {
	it("returns snake_case keys with id first and vendor_data last", () => {
		const keys = Object.keys(first("tenable", "vulnerabilities"));
		expect(keys[0]).toBe("id");
		expect(keys.at(-1)).toBe("vendor_data");
		for (const key of keys) {
			expect(key).toMatch(SNAKE);
		}
	});

	it("shapes vulnerabilities like Leen's findings", () => {
		const v = first("tenable", "vulnerabilities");
		expect(["open", "closed", "reopened", "ignored"]).toContain(v.state);
		expect(["critical", "high", "medium", "low", "info"]).toContain(v.severity);
		expect(v.vendor).toBe("tenable");
		expect(typeof v.cvss_base_score).toBe("number");
		expect(v).not.toHaveProperty("status");
		expect(Array.isArray(v.cve)).toBe(true);
		expect(typeof v.patchable).toBe("boolean");
	});

	it("shapes devices like Leen's Device", () => {
		const d = first("crowdstrike", "devices");
		expect(["active", "offline", "quarantined"]).toContain(d.status);
		expect(Array.isArray(d.hostnames)).toBe(true);
		expect(d.source_vendors).toEqual([
			expect.objectContaining({ vendor: "crowdstrike" }),
		]);
		expect(d.vendor_data).toEqual(
			expect.objectContaining({ vendor: "crowdstrike" })
		);
	});

	it("shapes detections like Leen's EDR alerts", () => {
		const a = first("crowdstrike", "detections");
		expect(a).toHaveProperty("first_event_time");
		expect(a).toHaveProperty("process_command_line");
		expect(a.verdict).toMatch(VERDICT);
		expect(a.mitre).toEqual([
			expect.objectContaining({ techniques: [expect.any(Object)] }),
		]);
	});

	it("shapes users like Leen's IDP users", () => {
		const u = first("okta", "users");
		expect(u).toHaveProperty("email_addr");
		expect(typeof u.is_mfa_enabled).toBe("boolean");
		expect(u).not.toHaveProperty("mfa");
	});
});
