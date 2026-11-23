// Turn the API's OpenAPI document into the one the docs site renders.
//
//   uv run --frozen securefabric-openapi | node apps/docs/scripts/openapi.mjs <out>
//   uv run --frozen securefabric-openapi | node apps/docs/scripts/openapi.mjs --check <out>
//
// The input is exactly what the API serves. Everything below is presentation for
// Mintlify; no path, parameter or schema is written by hand:
//
// - `servers` and `components.securitySchemes` so the playground can send requests.
// - Per-operation `security`: the scope each operation checks (`principal.require`
//   in packages/domain and apps/api, listed in SCOPES below), no credential for the
//   public catalogue, a connect session token for the hosted connect flow.
// - `Idempotency-Key` documented on the operations that honour it (IdempotencyDep).
// - Error responses typed as `application/problem+json`, which is what the API sends.
// - Operator-only and dashboard-session-only operations excluded (`x-excluded`).
// - Auto-generated Title Case summaries in sentence case, a few long summaries
//   shortened into page titles (the original moves to the description), and
//   internal requirement ids such as "(SEC-08)" removed.
// - Tags with display names and descriptions, in reading order.
// - Keys sorted, except where order is meaningful (paths, methods, properties), and
//   printed with two-space indentation, so a regenerated file diffs cleanly.
//
// `--check` exits 1 when <out> differs from what the current API would produce.

import { Buffer } from "node:buffer";
import { readFileSync, writeFileSync } from "node:fs";
import process from "node:process";

const SERVER = {
	description: "Production",
	url: "https://api.securefabric.dev",
};

const INFO_DESCRIPTION =
	"One API for vulnerability and application security data. Connect your customers' security tools, and SecureFabric syncs their findings and resources into one normalized, Leen V2-compatible model.";

const SECURITY_SCHEMES = {
	apiKey: {
		bearerFormat: "sfk_live_… or sfk_test_…",
		description:
			"An API key from the dashboard (Keys) or `POST /v1/api_keys`. Send it as `Authorization: Bearer sfk_…` or in the `X-API-KEY` header. A key belongs to one environment.",
		scheme: "bearer",
		type: "http",
	},
	connectSession: {
		bearerFormat: "sfcs_…",
		description:
			"The connect session token from `POST /v1/connect_sessions`. Valid for 30 minutes, only on `/v1/connect/*`.",
		scheme: "bearer",
		type: "http",
	},
};

// Tag name -> display name and description, in the order the sidebar shows them.
const TAGS = [
	[
		"account",
		"Account",
		"Who the caller is and which environments it can reach.",
	],
	["api_keys", "API keys", "Create, list and revoke API keys."],
	[
		"organizations",
		"Organizations",
		"Your end customers. Every connection belongs to one.",
	],
	[
		"connectors",
		"Connectors",
		"The public catalogue of vendors SecureFabric connects to.",
	],
	[
		"integrations",
		"Integrations",
		"Connectors enabled and configured in an environment, and your own vendor apps.",
	],
	[
		"connect",
		"Connect sessions",
		"Let your customers authorize a connection through the hosted connect flow.",
	],
	[
		"connections",
		"Connections",
		"One vendor tenant connected for one organization.",
	],
	["jobs", "Jobs", "Sync runs: request, follow and cancel them."],
	[
		"data",
		"Findings and resources",
		"The normalized, Leen V2-compatible data API.",
	],
	["actions", "Actions", "Write a finding's state back to the vendor."],
	[
		"webhooks",
		"Webhooks",
		"Endpoints, deliveries, replay, and the event feed.",
	],
	["events", "Events", "The event feed."],
	[
		"observability",
		"Operations and usage",
		"The operation log and usage counters.",
	],
	["status", "Status", "Service status."],
	["health", "Health", "Liveness and readiness probes."],
	["admin", "Admin", "Operator endpoints."],
];

// Operations that need no credentials, or accept a connect session token instead
// of an API key (see get_connect_principal in apps/api/src/securefabric_api/deps.py).
const PUBLIC = new Set([
	"connectors:list_connectors",
	"connectors:get_connector",
	"health:live",
	"health:ready",
]);
const OPTIONAL_AUTH = new Set(["status:get_status"]);
const CONNECT_SESSION = new Set([
	"connect:get_connect_session",
	"connect:connect_create_connection",
	"connect:connect_connection_status",
]);

// Creating POSTs that declare IdempotencyDep in apps/api/src/securefabric_api/routes.
const IDEMPOTENT = new Set([
	"organizations:create_organization",
	"api_keys:create_api_key",
	"integrations:create_integration",
	"integrations:create_vendor_app",
	"connections:create_connection",
	"connections:create_job",
	"connections:reset_connection",
	"connect:create_connect_session",
	"webhooks:create_webhook_endpoint",
	"actions:create_action",
]);

// The scope each operation requires: every `principal.require("<scope>")` on its
// path through apps/api/src/securefabric_api/routes and packages/domain. Shown on
// each endpoint page. Operations not listed accept any valid API key.
const SCOPES = {
	"actions:write": ["actions:create_action"],
	"data:read": [
		"data:list_vulnerability_findings",
		"data:findings_summary",
		"data:get_vulnerability_finding",
		"data:get_finding_history",
		"data:list_resources",
		"data:get_resource",
		"data:get_cve",
		"webhooks:list_events",
		"admin:passthrough",
	],
	"jobs:execute": [
		"connections:create_job",
		"connections:reset_connection",
		"jobs:cancel_job",
	],
	"keys:manage": [
		"api_keys:list_api_keys",
		"api_keys:create_api_key",
		"api_keys:revoke_api_key",
	],
	"provisioning:read": [
		"organizations:list_organizations",
		"organizations:get_organization",
		"integrations:list_integrations",
		"integrations:get_integration",
		"integrations:list_vendor_apps",
		"integrations:get_vendor_app",
		"connections:list_connections",
		"connections:get_connection",
		"connections:test_connection",
		"connections:connection_health_history",
		"connections:list_connection_jobs",
		"jobs:get_job",
		"jobs:get_job_logs",
		"connect:list_connect_sessions",
		"actions:get_action",
		"observability:list_operations",
		"observability:get_operation",
		"observability:get_usage",
	],
	"provisioning:write": [
		"organizations:create_organization",
		"organizations:update_organization",
		"organizations:delete_organization",
		"integrations:create_integration",
		"integrations:update_integration",
		"integrations:delete_integration",
		"integrations:create_vendor_app",
		"integrations:update_vendor_app",
		"integrations:delete_vendor_app",
		"connections:create_connection",
		"connections:update_connection",
		"connections:delete_connection",
		"connections:replace_connection_metadata",
		"connections:merge_connection_metadata",
		"connect:create_connect_session",
	],
	"webhooks:manage": [
		"webhooks:list_webhook_endpoints",
		"webhooks:create_webhook_endpoint",
		"webhooks:get_webhook_endpoint",
		"webhooks:update_webhook_endpoint",
		"webhooks:delete_webhook_endpoint",
		"webhooks:rotate_webhook_secret",
		"webhooks:ping_webhook_endpoint",
		"webhooks:list_webhook_deliveries",
		"webhooks:replay_webhook_delivery",
		"webhooks:replay_webhook_range",
	],
};
const SCOPE_OF = new Map(
	Object.entries(SCOPES).flatMap(([scope, ids]) => ids.map((id) => [id, scope]))
);

// Page titles for operations whose summary is a sentence rather than a name.
const TITLES = {
	"account:get_me": "Get the current caller",
	"account:list_environments": "List environments",
	"admin:passthrough": "Send a passthrough request",
	"connect:connect_connection_status":
		"Get connection status in a connect session",
	"connect:connect_create_connection":
		"Create a connection in a connect session",
	"connect:get_connect_session": "Get the connect session",
	"connections:connection_health_history": "Get connection health history",
	"connections:test_connection": "Test connection",
	"connectors:list_connectors": "List connectors",
	"data:findings_summary": "Summarize vulnerability findings",
	"data:get_cve": "Get CVE",
	"jobs:get_job_logs": "List job log lines",
	"observability:get_usage": "Get usage",
	"status:get_status": "Get status",
	"webhooks:list_events": "List events",
};

// Operations that accept any valid API key, whatever its scopes.
const ANY_KEY = new Set(["account:get_me", "account:list_environments"]);

// Not part of the customer API: SecureFabric operators (`require_operator`), and
// dashboard sessions only (`require_session`, an API key gets 403 session_required).
const SESSION_ONLY = new Set([
	"account:onboard",
	"account:create_environment",
	"account:update_environment",
	"account:list_members",
	"account:invite_member",
	"account:update_member",
	"account:remove_member",
	"account:list_audit_events",
	"account:get_audit_facets",
]);
const isExcluded = (path, op) =>
	SESSION_ONLY.has(op.operationId) ||
	path.startsWith("/v1/admin/") ||
	path.startsWith("/health/");

const ACRONYMS = { api: "API", cve: "CVE", id: "ID", ids: "IDs", url: "URL" };
const REQUIREMENT_IDS = /\s*\((?:[A-Z]+-\d+(?:\.\.[A-Z]+-\d+)?(?:,\s*)?)+\)/gu;
// Objects whose key order carries meaning: paths and the methods under each (the
// sidebar order), and schema properties (the field order on each page).
const ORDERED_KEYS = new Set(["paths", "path-item", "properties"]);

const titleCase = (name) =>
	name
		.split("_")
		.map((w) => w.charAt(0).toUpperCase() + w.slice(1))
		.join(" ");

const sentenceCase = (text) =>
	text
		.split(" ")
		.map((word, i) => {
			const lower = word.toLowerCase();
			if (ACRONYMS[lower]) {
				return ACRONYMS[lower];
			}
			return i === 0 ? word : lower;
		})
		.join(" ");

const stripIds = (text) => text.replace(REQUIREMENT_IDS, "").trim();

function cleanText(node) {
	if (Array.isArray(node)) {
		return node.map(cleanText);
	}
	if (node === null || typeof node !== "object") {
		return node;
	}
	const out = {};
	for (const [key, value] of Object.entries(node)) {
		out[key] =
			(key === "summary" || key === "description") && typeof value === "string"
				? stripIds(value)
				: cleanText(value);
	}
	return out;
}

function problemResponses(op) {
	for (const response of Object.values(op.responses ?? {})) {
		const content = response.content ?? {};
		const json = content["application/json"];
		if (
			content["application/problem+json"] &&
			json?.schema?.$ref === "#/components/schemas/Problem"
		) {
			response.content = {
				"application/problem+json": { schema: json.schema },
			};
		}
	}
	const invalid = op.responses?.["422"];
	if (
		invalid?.content?.["application/json"]?.schema?.$ref?.endsWith(
			"/HTTPValidationError"
		)
	) {
		invalid.content = {
			"application/problem+json": {
				schema: { $ref: "#/components/schemas/Problem" },
			},
		};
	}
}

function transformOperation(path, op) {
	const id = op.operationId;
	const name = id.split(":").at(-1);
	if (TITLES[id]) {
		op.description ??= `${op.summary}.`;
		op.summary = TITLES[id];
	} else if (op.summary === titleCase(name)) {
		op.summary = sentenceCase(op.summary);
	}
	if (PUBLIC.has(id)) {
		op.security = [];
	} else if (OPTIONAL_AUTH.has(id)) {
		op.security = [{}, { apiKey: [] }];
	} else if (CONNECT_SESSION.has(id)) {
		op.security = [{ connectSession: [] }];
	} else if (SCOPE_OF.has(id)) {
		op.security = [{ apiKey: [SCOPE_OF.get(id)] }];
	}
	if (IDEMPOTENT.has(id)) {
		op.parameters = [
			...(op.parameters ?? []),
			{
				description:
					"A unique value per logical request. A retry with the same key within 24 hours returns the first response with `Idempotent-Replayed: true`.",
				in: "header",
				name: "Idempotency-Key",
				required: id === "actions:create_action",
				schema: { maxLength: 255, type: "string" },
			},
		];
	}
	// An operation's first tag picks its sidebar group. The passthrough is tagged
	// admin and connections; it is a customer endpoint, so it goes with connections.
	if (op.tags?.includes("admin") && op.tags.length > 1) {
		op.tags = op.tags.filter((tag) => tag !== "admin");
	}
	if (isExcluded(path, op)) {
		op["x-excluded"] = true;
	}
	problemResponses(op);
	return op;
}

// Fail on a list entry that names no operation (a renamed route), and warn about
// a customer operation this script does not know the scope of (a new route).
function checkReferences(spec) {
	const ops = Object.values(spec.paths).flatMap((item) => Object.values(item));
	const ids = new Set(ops.map((op) => op.operationId));
	const listed = [
		...PUBLIC,
		...OPTIONAL_AUTH,
		...CONNECT_SESSION,
		...IDEMPOTENT,
		...ANY_KEY,
		...SCOPE_OF.keys(),
		...Object.keys(TITLES),
	];
	const stale = listed.filter((id) => !ids.has(id));
	if (stale.length > 0) {
		throw new Error(
			`scripts/openapi.mjs names unknown operations: ${stale.join(", ")}`
		);
	}
	for (const op of ops) {
		const id = op.operationId;
		const covered =
			op["x-excluded"] ||
			SCOPE_OF.has(id) ||
			ANY_KEY.has(id) ||
			PUBLIC.has(id) ||
			OPTIONAL_AUTH.has(id) ||
			CONNECT_SESSION.has(id);
		if (!covered) {
			process.stderr.write(
				`warning: no scope listed for ${id} in scripts/openapi.mjs\n`
			);
		}
	}
}

function sortKeys(node, parentKey) {
	if (Array.isArray(node)) {
		return node.map((item) => sortKeys(item));
	}
	if (node === null || typeof node !== "object") {
		return node;
	}
	const keys = Object.keys(node);
	if (!ORDERED_KEYS.has(parentKey)) {
		keys.sort();
	}
	const out = {};
	for (const key of keys) {
		out[key] = sortKeys(node[key], parentKey === "paths" ? "path-item" : key);
	}
	return out;
}

export function transform(source) {
	const spec = cleanText(structuredClone(source));
	spec.info.description = INFO_DESCRIPTION;
	spec.servers = [SERVER];
	spec.security = [{ apiKey: [] }];
	spec.components.securitySchemes = SECURITY_SCHEMES;
	const used = new Set();
	for (const [path, item] of Object.entries(spec.paths)) {
		for (const op of Object.values(item)) {
			transformOperation(path, op);
			if (!op["x-excluded"] && op.tags?.length) {
				used.add(op.tags[0]);
			}
		}
	}
	checkReferences(spec);
	// Mintlify orders sidebar groups by first appearance, so order paths by tag.
	const rank = (item) => {
		const tag = Object.values(item)[0]?.tags?.[0];
		const i = TAGS.findIndex(([name]) => name === tag);
		return i === -1 ? TAGS.length : i;
	};
	spec.paths = Object.fromEntries(
		Object.entries(spec.paths)
			.map((entry, i) => [entry, i])
			.sort(([a, i], [b, j]) => rank(a[1]) - rank(b[1]) || i - j)
			.map(([entry]) => entry)
	);
	const known = new Set(TAGS.map(([name]) => name));
	spec.tags = [
		...TAGS.filter(([name]) => used.has(name)).map(
			([name, displayName, description]) => ({
				description,
				name,
				"x-displayName": displayName,
			})
		),
		...[...used].filter((name) => !known.has(name)).map((name) => ({ name })),
	];
	return sortKeys(spec);
}

async function readStdin() {
	const chunks = [];
	for await (const chunk of process.stdin) {
		chunks.push(chunk);
	}
	return Buffer.concat(chunks).toString("utf8");
}

async function main() {
	const args = process.argv.slice(2);
	const check = args[0] === "--check";
	const out = check ? args[1] : args[0];
	if (!out) {
		process.stderr.write(
			"usage: openapi.mjs [--check] <out.json> < openapi.json\n"
		);
		process.exit(2);
	}
	const source = JSON.parse(await readStdin());
	const text = `${JSON.stringify(transform(source), null, 2)}\n`;
	if (!check) {
		writeFileSync(out, text);
		process.stdout.write(`wrote ${out}\n`);
		return;
	}
	let current = "";
	try {
		current = readFileSync(out, "utf8");
	} catch {
		// A missing file is stale too.
	}
	if (current !== text) {
		process.stderr.write(
			`${out} is out of date with the API. Run: pnpm -F docs generate\n`
		);
		process.exit(1);
	}
}

await main();
