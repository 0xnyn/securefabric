/** Code samples in the three languages the docs use, generated from the
 * request a page is showing so keys and IDs are always the real ones. */

export const API_BASE = "https://api.securefabric.dev";

export interface RequestSpec {
	body?: Record<string, unknown>;
	connectionId?: string;
	method: "GET" | "POST" | "PATCH" | "DELETE";
	path: string;
	query?: Record<string, string | string[]>;
	/** SDK resource and method, e.g. ["vulnerabilities", "list"]. */
	sdk?: [string, string];
	secretKey: string;
}

function queryString(query: RequestSpec["query"]): string {
	if (!query) {
		return "";
	}
	const parts: string[] = [];
	for (const [k, v] of Object.entries(query)) {
		const value = Array.isArray(v) ? v.join(",") : v;
		if (value !== "") {
			parts.push(`${k}=${encodeURIComponent(value).replaceAll("%2C", ",")}`);
		}
	}
	return parts.length ? `?${parts.join("&")}` : "";
}

const CAMEL = /_(?<ch>[a-z])/gu;

function camel(key: string): string {
	return key.replace(CAMEL, (_, ch: string) => ch.toUpperCase());
}

const UPPER = /[A-Z]/gu;
const DIGITS = /^\d+$/u;
const DASH_CHAR = /-(?<ch>[a-z])/gu;

function snake(key: string): string {
	return key.replace(UPPER, (ch) => `_${ch.toLowerCase()}`);
}

function tsValue(v: unknown): string {
	if (Array.isArray(v)) {
		return `[${v.map((x) => JSON.stringify(x)).join(", ")}]`;
	}
	return JSON.stringify(v);
}

function pyValue(v: unknown): string {
	if (Array.isArray(v)) {
		return `[${v.map((x) => JSON.stringify(x)).join(", ")}]`;
	}
	if (typeof v === "boolean") {
		return v ? "True" : "False";
	}
	return JSON.stringify(v);
}

export function curl(spec: RequestSpec): string {
	const lines = [
		`curl ${spec.method === "GET" ? "" : `-X ${spec.method} `}"${API_BASE}${spec.path}${queryString(spec.query)}" \\`,
		`  -H "X-API-Key: ${spec.secretKey}"${spec.connectionId || spec.body ? " \\" : ""}`,
	];
	if (spec.connectionId) {
		lines.push(
			`  -H "X-Connection-Id: ${spec.connectionId}"${spec.body ? " \\" : ""}`
		);
	}
	if (spec.body) {
		lines.push(`  -H "Content-Type: application/json" \\`);
		lines.push(`  -d '${JSON.stringify(spec.body)}'`);
	}
	return lines.join("\n");
}

function sdkArgs(spec: RequestSpec): [string, unknown][] {
	const args: [string, unknown][] = [];
	if (spec.connectionId) {
		args.push(["connectionId", spec.connectionId]);
	}
	for (const [k, v] of Object.entries(spec.query ?? {})) {
		if (v !== "" && !(Array.isArray(v) && v.length === 0)) {
			args.push([camel(k), Array.isArray(v) ? v : coerce(v)]);
		}
	}
	for (const [k, v] of Object.entries(spec.body ?? {})) {
		args.push([camel(k), v]);
	}
	return args;
}

function coerce(v: string): unknown {
	if (v === "true" || v === "false") {
		return v === "true";
	}
	if (DIGITS.test(v)) {
		return Number(v);
	}
	return v;
}

export function typescript(spec: RequestSpec): string {
	const [resource, method] = spec.sdk ?? ["request", spec.method.toLowerCase()];
	const args = sdkArgs(spec);
	const body = args.map(([k, v]) => `  ${k}: ${tsValue(v)},`).join("\n");
	const call = method === "list" ? "const { items, total }" : "const result";
	return [
		`import { SecureFabric } from "@securefabric/sdk";`,
		"",
		"const securefabric = new SecureFabric(process.env.SECUREFABRIC_API_KEY);",
		"",
		`${call} = await securefabric.${resource}.${method}({`,
		body,
		"});",
	].join("\n");
}

export function python(spec: RequestSpec): string {
	const [resource, method] = spec.sdk ?? ["request", spec.method.toLowerCase()];
	const args = sdkArgs(spec);
	const body = args
		.map(([k, v]) => `    ${snake(k)}=${pyValue(v)},`)
		.join("\n");
	return [
		"import os",
		"from securefabric import SecureFabric",
		"",
		`securefabric = SecureFabric(os.environ["SECUREFABRIC_API_KEY"])`,
		"",
		`page = securefabric.${resource.replaceAll("-", "_")}.${method}(`,
		body,
		")",
	].join("\n");
}

export function samples(spec: RequestSpec): { label: string; code: string }[] {
	return [
		{ code: curl(spec), label: "cURL" },
		{ code: typescript(spec), label: "TypeScript" },
		{ code: python(spec), label: "Python" },
	];
}

export function sdkResource(path: string): string {
	const seg = path.split("/")[2] ?? "request";
	return seg.replace(DASH_CHAR, (_, ch: string) => ch.toUpperCase());
}
