/** The public API surface the playground can call, and a simulated server
 * that answers from a connection's generated records. */

import { apiPath } from "./api-paths";
import { getProvider, MODELS, type ModelKey } from "./catalog";
import { createRng, makeId } from "./random";
import { generateRecords, type Json, type JsonObject } from "./records";
import {
	type Connection,
	type Environment,
	FREQUENCY_MS,
	HEALTH,
} from "./types";
import { errorBody, toWire, vendorCode, wireField } from "./wire";

export type ParamType =
	| "multi"
	| "enum"
	| "string"
	| "number"
	| "boolean"
	| "datetime";

export interface Param {
	default?: string;
	description: string;
	name: string;
	options?: string[];
	required?: boolean;
	type: ParamType;
}

export interface Endpoint {
	/** Body fields for writes. */
	body?: Param[];
	description: string;
	group: "Unified models" | "Actions" | "Platform";
	id: string;
	kind: "list" | "get" | "action" | "passthrough" | "connections";
	method: "GET" | "POST" | "PATCH";
	model?: ModelKey;
	params: Param[];
	path: string;
	scope?: string;
	title: string;
}

/** Leen v1 paging: offset pages with a total by default; cursor pages when
 * enableCursor is true. */
const PAGING: Param[] = [
	{
		default: "100",
		description: "Records per page, 1 to 500.",
		name: "limit",
		type: "number",
	},
	{
		default: "0",
		description: "Records to skip. Ignored when enableCursor is true.",
		name: "offset",
		type: "number",
	},
	{
		description: "Only records updated after this time (ISO 8601).",
		name: "updatedSince",
		type: "datetime",
	},
	{
		description:
			"Return cursor pages ({items, next_cursor, previous_cursor}) instead of offset pages.",
		name: "enableCursor",
		options: ["true", "false"],
		type: "boolean",
	},
	{
		description: "Opaque cursor from a previous page's next_cursor.",
		name: "cursor",
		type: "string",
	},
];

const SEVERITY: Param = {
	description: "Normalized severity. Comma-separated.",
	name: "severity",
	options: ["critical", "high", "medium", "low", "info"],
	type: "multi",
};

const FILTERS: Partial<Record<ModelKey, Param[]>> = {
	"cloud-findings": [
		SEVERITY,
		{
			description: "Finding state.",
			name: "status",
			options: ["open", "resolved", "ignored"],
			type: "enum",
		},
	],
	"cloud-resources": [
		{
			description: "Cloud provider.",
			name: "cloud",
			options: ["aws", "azure", "gcp"],
			type: "enum",
		},
		{
			description: "Only resources reachable from the internet.",
			name: "internetExposed",
			options: ["true", "false"],
			type: "boolean",
		},
	],
	"code-findings": [
		SEVERITY,
		{
			description: "Finding type.",
			name: "type",
			options: ["dependency", "code", "secret", "iac"],
			type: "enum",
		},
	],
	detections: [
		SEVERITY,
		{
			description: "Triage state.",
			name: "status",
			options: ["new", "in_progress", "resolved"],
			type: "enum",
		},
	],
	devices: [
		{
			description: "Operating system family.",
			name: "platform",
			options: ["linux", "windows", "mac"],
			type: "enum",
		},
		{
			description: "Device state.",
			name: "status",
			options: ["active", "offline", "quarantined"],
			type: "enum",
		},
	],
	users: [
		{
			description: "Account status in the identity provider.",
			name: "vendorStatus",
			options: ["ACTIVE", "SUSPENDED", "DEPROVISIONED"],
			type: "enum",
		},
		{
			description: "Filter by MFA enrolment.",
			name: "mfaEnabled",
			options: ["true", "false"],
			type: "boolean",
		},
	],
	vulnerabilities: [
		SEVERITY,
		{
			description: "Lifecycle state.",
			name: "state",
			options: ["open", "closed", "reopened", "ignored"],
			type: "enum",
		},
		{
			description: "Only CVEs with known exploitation.",
			name: "exploitable",
			options: ["true", "false"],
			type: "boolean",
		},
	],
};

const LIST_TITLES: Record<ModelKey, string> = {
	alerts: "alerts",
	"cloud-findings": "cloud findings",
	"cloud-resources": "cloud resources",
	"code-findings": "code findings",
	controls: "controls",
	detections: "detections",
	devices: "devices",
	"email-threats": "email threats",
	groups: "groups",
	indicators: "indicators",
	repositories: "repositories",
	tickets: "tickets",
	users: "users",
	vendors: "vendors",
	vulnerabilities: "vulnerabilities",
};

const LIST_MODELS: ModelKey[] = [
	"vulnerabilities",
	"devices",
	"detections",
	"cloud-findings",
	"cloud-resources",
	"users",
	"groups",
	"code-findings",
	"repositories",
	"tickets",
	"alerts",
];

export const ENDPOINTS: Endpoint[] = [
	...LIST_MODELS.map(
		(m): Endpoint => ({
			description: MODELS[m].description,
			group: "Unified models",
			id: `list-${m}`,
			kind: "list",
			method: "GET",
			model: m,
			params: [...(FILTERS[m] ?? []), ...PAGING],
			path: apiPath(m),
			scope: MODELS[m].scope,
			title: `List ${LIST_TITLES[m]}`,
		})
	),
	{
		description: "One vulnerability by ID, with every source that reported it.",
		group: "Unified models",
		id: "get-vulnerability",
		kind: "get",
		method: "GET",
		model: "vulnerabilities",
		params: [
			{
				description: "Vulnerability ID.",
				name: "id",
				required: true,
				type: "string",
			},
		],
		path: "/v1/vulnerabilities/{id}",
		scope: "vulnerabilities:read",
		title: "Retrieve a vulnerability",
	},
	{
		body: [
			{
				default: "Detection escalated by on-call",
				description: "Recorded on the vendor's audit log.",
				name: "reason",
				type: "string",
			},
		],
		description:
			"Network-contain a host through the connected EDR. Asynchronous: returns pending, then sends action.completed.",
		group: "Actions",
		id: "isolate-device",
		kind: "action",
		method: "POST",
		model: "devices",
		params: [
			{ description: "Device ID.", name: "id", required: true, type: "string" },
		],
		path: "/v1/devices/{id}/isolate",
		scope: "devices:isolate",
		title: "Isolate a device",
	},
	{
		body: [
			{
				default: "CVE-2024-3094 on api-prod-03",
				description: "Ticket summary.",
				name: "title",
				type: "string",
			},
			{
				default: "high",
				description: "Normalized priority.",
				name: "priority",
				options: ["highest", "high", "medium", "low"],
				type: "enum",
			},
		],
		description: "Create a ticket in the connected Jira or ServiceNow project.",
		group: "Actions",
		id: "create-ticket",
		kind: "action",
		method: "POST",
		model: "tickets",
		params: [],
		path: "/v1/tickets",
		scope: "tickets:write",
		title: "Create a ticket",
	},
	{
		body: [
			{
				default: "Offboarded",
				description: "Why the account is being suspended.",
				name: "reason",
				type: "string",
			},
		],
		description: "Suspend a user in the connected identity provider.",
		group: "Actions",
		id: "suspend-user",
		kind: "action",
		method: "POST",
		model: "users",
		params: [
			{ description: "User ID.", name: "id", required: true, type: "string" },
		],
		path: "/v1/users/{id}/suspend",
		scope: "identities:write",
		title: "Suspend a user",
	},
	{
		body: [
			{
				default: "GET",
				description: "HTTP method for the vendor call.",
				name: "method",
				options: ["GET", "POST"],
				type: "enum",
			},
			{
				default: "/",
				description: "Path on the vendor's API.",
				name: "path",
				type: "string",
			},
		],
		description:
			"Call any vendor endpoint with the connection's stored credentials. SecureFabric handles auth, token refresh and rate limits.",
		group: "Platform",
		id: "passthrough",
		kind: "passthrough",
		method: "POST",
		params: [],
		path: "/v1/passthrough",
		title: "Passthrough request",
	},
	{
		description: "Every connection in this environment, filterable by tag.",
		group: "Platform",
		id: "list-connections",
		kind: "connections",
		method: "GET",
		params: [
			{
				description: "Filter by integration ID.",
				name: "integrationId",
				type: "string",
			},
			{
				description: "Filter by tag, as key:value.",
				name: "tag",
				type: "string",
			},
		],
		path: "/v1/connections",
		title: "List connections",
	},
];

export interface SimResponse {
	body: Json;
	durationMs: number;
	headers: Record<string, string>;
	records: number;
	status: number;
}

function matches(
	r: JsonObject,
	params: Record<string, string>,
	filters: Param[]
): boolean {
	for (const f of filters) {
		const want = params[f.name];
		if (!want) {
			continue;
		}
		const got = wireField(r, f.name);
		if (f.type === "multi") {
			if (!want.split(",").includes(String(got))) {
				return false;
			}
		} else if (String(got) !== want) {
			return false;
		}
	}
	const since = params.updatedSince
		? Date.parse(params.updatedSince)
		: Number.NaN;
	if (!Number.isNaN(since)) {
		const updated = r.updated_at ?? r.last_seen ?? r.first_seen;
		if (typeof updated === "string" && Date.parse(updated) < since) {
			return false;
		}
	}
	return true;
}

function error(
	status: number,
	type: string,
	message: string,
	rid: string,
	detail: JsonObject[] = []
): SimResponse {
	return {
		body: errorBody(status, type, message, detail),
		durationMs: 40,
		headers: { "x-request-id": rid },
		records: 0,
		status,
	};
}

function supports(
	env: Environment,
	conn: Connection,
	model: ModelKey
): boolean {
	const integration = env.integrations.find((i) => i.id === conn.integrationId);
	return (
		integration?.models ??
		getProvider(conn.provider)?.models ??
		[]
	).includes(model);
}

function listResponse(
	conn: Connection,
	ep: Endpoint,
	params: Record<string, string>,
	rid: string
): SimResponse {
	const model = ep.model as ModelKey;
	const limit = Math.min(500, Math.max(1, Number(params.limit) || 100));
	const records = generateRecords(
		conn.id,
		conn.provider,
		model,
		conn.domain,
		conn.lastSyncAt ?? conn.createdAt,
		100
	);
	const filters = FILTERS[model] ?? [];
	const wire = records.map((r) => toWire(model, r));
	const filtered = wire.filter((r) => matches(r, params, filters));
	const useCursor = params.enableCursor === "true";
	let offset = Math.max(0, Number.parseInt(params.offset, 10) || 0);
	if (useCursor) {
		offset = params.cursor
			? Number.parseInt(atob(params.cursor).split(":")[1] ?? "0", 10) || 0
			: 0;
	}
	const page = filtered.slice(offset, offset + limit);
	const ratio = filtered.length / Math.max(1, records.length);
	const total = Math.round((conn.counts[model] ?? records.length) * ratio);
	const more = offset + limit < total;
	return {
		body: useCursor
			? {
					items: page,
					next_cursor: more ? btoa(`${model}:${offset + limit}`) : null,
					previous_cursor:
						offset > 0 ? btoa(`${model}:${Math.max(0, offset - limit)}`) : null,
				}
			: { count: page.length, items: page, total },
		durationMs: 0,
		headers: {
			"x-request-id": rid,
			"x-securefabric-synced-at": new Date(
				conn.lastSyncAt ?? conn.createdAt
			).toISOString(),
			...(conn.health === "UNAUTHORIZED"
				? { "x-securefabric-stale": "true" }
				: {}),
		},
		records: page.length,
		status: 200,
	};
}

function actionResponse(
	env: Environment,
	conn: Connection,
	ep: Endpoint,
	params: Record<string, string>,
	body: Record<string, string>,
	rid: string
): SimResponse {
	const integration = env.integrations.find((i) => i.id === conn.integrationId);
	const writes = getProvider(conn.provider)?.writeActions ?? [];
	if (!writes.some((w) => w.scope === ep.scope)) {
		return error(
			400,
			"unsupported_action",
			`${getProvider(conn.provider)?.name} connections don't support ${ep.scope}.`,
			rid
		);
	}
	if (!integration?.writeScopes.includes(ep.scope ?? "")) {
		return error(
			403,
			"scope_not_granted",
			`The ${ep.scope} scope isn't enabled for ${integration?.id}. Turn it on under Integrations → Configuration.`,
			rid
		);
	}
	return {
		body: {
			connection_id: conn.id,
			created_at: new Date().toISOString(),
			id: makeId("act", createRng(rid)),
			input: { ...params, ...body },
			status: "PENDING",
			type: (ep.scope ?? "").replace(":", "_").toUpperCase(),
		},
		durationMs: 0,
		headers: { "x-request-id": rid },
		records: 0,
		status: 202,
	};
}

/** Leen's connection health: a status, a named cause, and who has to act. */
function connectionHealth(c: Connection): JsonObject {
	const info = HEALTH[c.health];
	let status = "UNHEALTHY";
	if (c.health === "HEALTHY" || c.health === "PAUSED") {
		status = "HEALTHY";
	} else if (c.health === "SYNCING") {
		status = "INITIALIZING";
	}
	const owners: Record<typeof info.owner, string> = {
		Customer: "CUSTOMER",
		SecureFabric: "SECUREFABRIC",
		Vendor: "VENDOR",
		You: "CUSTOMER",
	};
	return {
		description: info.description,
		name: c.health === "SYNCING" ? "INITIALIZING" : c.health,
		resolution_owner: owners[info.owner],
		status,
	};
}

const SECOND = 1000;

/** Leen's connection, with SecureFabric's customer, sandbox and tag fields. */
function connectionWire(c: Connection, env: Environment): JsonObject {
	const integration = env.integrations.find((i) => i.id === c.integrationId);
	const frequency = c.frequencyOverride ?? integration?.syncFrequency;
	const updatedAt = c.lastSyncAt ?? c.createdAt;
	return {
		created_at: new Date(c.createdAt).toISOString(),
		customer: c.customer.orgName,
		direction: "SOURCE",
		health: connectionHealth(c),
		id: c.id,
		identifier: c.customer.endUserId,
		integration_id: c.integrationId,
		is_active: !c.paused,
		last_synced_at: c.lastSyncAt ? new Date(c.lastSyncAt).toISOString() : null,
		refresh_interval_secs: frequency ? FREQUENCY_MS[frequency] / SECOND : null,
		sandbox: c.sandbox,
		state: c.paused ? "PAUSED" : "ACTIVE",
		tags: c.tags,
		updated_at: new Date(updatedAt).toISOString(),
		vendor: vendorCode(c.provider),
	};
}

export function simulate(
	env: Environment,
	ep: Endpoint,
	conn: Connection | null,
	params: Record<string, string>,
	body: Record<string, string>
): SimResponse {
	const rid = makeId("req", createRng(`${Date.now()}:${Math.random()}`), 16);
	const rng = createRng(rid);
	const respond = (r: SimResponse): SimResponse => ({
		...r,
		durationMs: rng.int(45, r.status >= 400 ? 120 : 380),
		headers: { ...r.headers, "x-ratelimit-remaining": String(rng.int(80, 99)) },
	});

	if (ep.kind === "connections") {
		const rows = env.connections.filter(
			(c) => !params.integrationId || c.integrationId === params.integrationId
		);
		return respond({
			body: {
				count: rows.length,
				items: rows.map((c) => connectionWire(c, env)),
				total: rows.length,
			},
			durationMs: 0,
			headers: { "x-request-id": rid },
			records: rows.length,
			status: 200,
		});
	}
	if (!conn) {
		return respond(
			error(
				400,
				"missing_connection",
				"Pass a connection ID in the X-Connection-Id header.",
				rid
			)
		);
	}
	if (conn.health === "SYNCING" && !conn.lastSyncAt) {
		return respond(
			error(
				409,
				"initial_sync_in_progress",
				"The initial sync hasn't finished. Retry shortly, or wait for the connection.sync.succeeded webhook.",
				rid
			)
		);
	}
	if (ep.model && !supports(env, conn, ep.model)) {
		return respond(
			error(
				404,
				"model_not_supported",
				`${getProvider(conn.provider)?.name} (${conn.integrationId}) doesn't provide ${MODELS[ep.model].name} records.`,
				rid
			)
		);
	}
	for (const p of ep.params) {
		if (p.required && !params[p.name]) {
			return respond(
				error(422, "validation_error", `"${p.name}" is required.`, rid, [
					{ loc: ["path", p.name], msg: "Field required", type: "missing" },
				])
			);
		}
	}
	if (ep.kind === "list") {
		if (params.cursor && params.updatedSince) {
			return respond(
				error(
					422,
					"validation_error",
					'"updatedSince" cannot be combined with "cursor".',
					rid,
					[
						{
							loc: ["query", "updatedSince"],
							msg: "Not allowed together with cursor",
							type: "value_error",
						},
					]
				)
			);
		}
		return respond(listResponse(conn, ep, params, rid));
	}
	if (ep.kind === "get") {
		const all = generateRecords(
			conn.id,
			conn.provider,
			ep.model as ModelKey,
			conn.domain,
			conn.lastSyncAt ?? conn.createdAt,
			100
		);
		const hit = all.find((r) => r.id === params.id);
		return respond(
			hit
				? {
						body: toWire("vulnerabilities", hit),
						durationMs: 0,
						headers: { "x-request-id": rid },
						records: 1,
						status: 200,
					}
				: error(
						404,
						"not_found",
						`No vulnerability ${params.id} on this connection.`,
						rid
					)
		);
	}
	if (ep.kind === "passthrough") {
		return respond({
			body: {
				data: {
					note: `Vendor response from ${getProvider(conn.provider)?.name}, passed through unchanged.`,
					path: body.path || "/",
				},
				status: 200,
			},
			durationMs: 0,
			headers: { "x-request-id": rid, "x-securefabric-vendor-status": "200" },
			records: 0,
			status: 200,
		});
	}
	return respond(actionResponse(env, conn, ep, params, body, rid));
}

/** The first record ID for a connection and model, to prefill {id}. */
export function sampleId(
	conn: Connection | null,
	model: ModelKey | undefined
): string {
	if (!(conn && model)) {
		return "";
	}
	return (
		generateRecords(
			conn.id,
			conn.provider,
			model,
			conn.domain,
			conn.lastSyncAt ?? conn.createdAt,
			100
		)[0]?.id ?? ""
	);
}
