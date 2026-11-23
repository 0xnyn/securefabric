import { describe, expect, it } from "vitest";
import {
	CONNECTOR_LOGOS,
	categoryOf,
	everySeconds,
	PLANNED,
	RELEASES,
	typeLabel,
} from "./connector-catalog";

describe("connector catalog", () => {
	it("lists every planned connector once, with a known release", () => {
		const ids = PLANNED.map((p) => p.id);
		expect(new Set(ids).size).toBe(ids.length);
		for (const p of PLANNED) {
			expect(RELEASES[p.release]).toBeDefined();
		}
		// Tier A (10), tier B (6), tier C (10) and detection (7).
		expect(PLANNED.filter((p) => p.release === "february")).toHaveLength(10);
		expect(PLANNED.filter((p) => p.release === "partner")).toHaveLength(6);
		expect(PLANNED.filter((p) => p.release === "spring")).toHaveLength(10);
	});

	it("gives dark-on-transparent marks a light twin", () => {
		for (const id of ["GITHUB", "AWS_INSPECTOR2", "SNYK"]) {
			expect(CONNECTOR_LOGOS[id]?.dark).toBeTruthy();
		}
	});

	it("maps manifest categories and enums to words", () => {
		expect(categoryOf(["appsec", "code"])).toBe("code");
		expect(categoryOf(["sandbox", "appsec"])).toBe("testing");
		expect(categoryOf(["vulnerability_management"])).toBe("vulnerability");
		expect(typeLabel("IAC")).toBe("Infrastructure as code");
		expect(typeLabel("NEW_THING")).toBe("New thing");
		expect(everySeconds(3600)).toBe("every hour");
		expect(everySeconds(900)).toBe("every 15 minutes");
		expect(everySeconds(86_400)).toBe("every day");
	});
});
