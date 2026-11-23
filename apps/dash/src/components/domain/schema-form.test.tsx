// @vitest-environment jsdom

import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	compactValues,
	defaultsFor,
	type FormValues,
	type JsonSchema,
	orderedFields,
	SchemaForm,
	validate,
} from "./schema-form";

(
	globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

/** Shaped like a real connector's credentials schema (no connector code involved). */
const SCHEMA: JsonSchema = {
	properties: {
		api_key: {
			description: "Settings → API keys",
			pattern: "^key_[a-z0-9]{8}$",
			title: "API key",
			"x-order": 1,
			"x-secret": true,
		},
		fingerprint: { readOnly: true, type: "string" },
		page_size: { default: 50, maximum: 100, minimum: 10, type: "integer" },
		region: {
			default: "us",
			enum: ["us", "eu"],
			title: "Region",
			"x-order": 2,
		},
		tenant: { title: "Tenant", type: "string", "x-order": 0 },
		verify_tls: { default: true, title: "Verify TLS", type: "boolean" },
	},
	required: ["tenant", "api_key"],
	type: "object",
};

describe("schema helpers", () => {
	it("orders by x-order, then declaration order, and hides readOnly fields", () => {
		expect(orderedFields(SCHEMA).map(([n]) => n)).toEqual([
			"tenant",
			"api_key",
			"region",
			"page_size",
			"verify_tls",
		]);
	});

	it("fills defaults and lets presets win", () => {
		expect(defaultsFor(SCHEMA, { region: "eu" })).toEqual({
			page_size: 50,
			region: "eu",
			verify_tls: true,
		});
	});

	it("checks required, pattern and range", () => {
		expect(validate(SCHEMA, { page_size: 5 })).toEqual({
			api_key: "Enter the API key",
			page_size: "Enter 10 or more",
			tenant: "Enter the tenant",
		});
		expect(
			validate(SCHEMA, { api_key: "nope", page_size: 500, tenant: "acme" })
		).toEqual({
			api_key:
				"This doesn't look like a valid API key. Check for missing characters or extra spaces.",
			page_size: "Enter 100 or less",
		});
		expect(
			validate(SCHEMA, { api_key: "key_abcd1234", tenant: "acme" })
		).toEqual({});
	});

	it("drops empty values before sending", () => {
		expect(
			compactValues({ a: "", b: undefined, c: 0, d: false, e: "x" })
		).toEqual({ c: 0, d: false, e: "x" });
	});
});

function Harness({
	onChange,
	errors,
}: {
	onChange: (v: FormValues) => void;
	errors?: Record<string, string>;
}) {
	const [values, setValues] = useState<FormValues>(defaultsFor(SCHEMA));
	return (
		<SchemaForm
			errors={errors}
			idPrefix="t"
			onChange={(v) => {
				setValues(v);
				onChange(v);
			}}
			schema={SCHEMA}
			values={values}
		/>
	);
}

describe("<SchemaForm>", () => {
	let container: HTMLDivElement;
	let root: Root;
	beforeEach(() => {
		container = document.createElement("div");
		document.body.append(container);
		root = createRoot(container);
	});
	afterEach(() => {
		act(() => root.unmount());
		container.remove();
	});

	function type(input: HTMLInputElement, value: string) {
		const setter = Object.getOwnPropertyDescriptor(
			HTMLInputElement.prototype,
			"value"
		)?.set;
		setter?.call(input, value);
		input.dispatchEvent(new Event("input", { bubbles: true }));
	}

	it("renders every field from the schema, in order, with secrets masked", () => {
		act(() => root.render(<Harness onChange={() => undefined} />));
		const labels = [...container.querySelectorAll("label")].map(
			(l) => l.textContent
		);
		expect(labels).toEqual([
			"Tenant",
			"API key",
			"Region (optional)",
			"Page size (optional)",
		]);
		expect(container.textContent).toContain("Verify TLS");
		expect(container.querySelector<HTMLInputElement>("#t-api_key")?.type).toBe(
			"password"
		);
		expect(container.querySelector<HTMLInputElement>("#t-tenant")?.type).toBe(
			"text"
		);
		expect(
			container.querySelector<HTMLInputElement>("#t-page_size")?.type
		).toBe("number");
		expect(
			container.querySelector<HTMLInputElement>("#t-page_size")?.value
		).toBe("50");
		expect(container.querySelector("#t-fingerprint")).toBeNull();
		expect(container.textContent).toContain("Settings → API keys");
	});

	it("reports typed values, numbers as numbers", () => {
		const onChange = vi.fn();
		act(() => root.render(<Harness onChange={onChange} />));
		act(() =>
			type(
				container.querySelector<HTMLInputElement>(
					"#t-tenant"
				) as HTMLInputElement,
				"acme"
			)
		);
		expect(onChange).toHaveBeenLastCalledWith(
			expect.objectContaining({ tenant: "acme" })
		);
		act(() =>
			type(
				container.querySelector<HTMLInputElement>(
					"#t-page_size"
				) as HTMLInputElement,
				"75"
			)
		);
		expect(onChange).toHaveBeenLastCalledWith(
			expect.objectContaining({ page_size: 75, tenant: "acme" })
		);
	});

	it("shows field errors in place of the description", () => {
		act(() =>
			root.render(
				<Harness
					errors={{
						api_key:
							"This doesn't look like a valid API key. Check for missing characters or extra spaces.",
					}}
					onChange={() => undefined}
				/>
			)
		);
		const alert = container.querySelector("[role=alert]");
		expect(alert?.textContent).toBe(
			"This doesn't look like a valid API key. Check for missing characters or extra spaces."
		);
		expect(
			container.querySelector("#t-api_key")?.getAttribute("aria-invalid")
		).toBe("true");
		expect(container.textContent).not.toContain("Settings → API keys");
	});

	it("renders nothing for a schema without inputs", () => {
		act(() =>
			root.render(
				<SchemaForm
					onChange={() => undefined}
					schema={{ properties: {}, type: "object" }}
					values={{}}
				/>
			)
		);
		expect(container.innerHTML).toBe("");
	});
});
