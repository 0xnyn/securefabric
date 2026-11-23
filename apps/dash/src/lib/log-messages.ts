/** The messages inside an operation, generated from its ID so they're
 * stable and never stored. They mirror what the real pipeline logs: vendor
 * HTTP calls, pagination, normalization, checkpoints, webhook deliveries. */

import { getProvider, MODELS, type ModelKey } from "./catalog";
import { createRng, type Rng } from "./random";
import type { Environment, Operation } from "./types";

export type Level = "info" | "warn" | "error" | "http";

export interface LogMessage {
	at: number;
	http?: { method: string; status: number; url: string; ms: number };
	level: Level;
	text: string;
}

const VENDOR_HOSTS: Record<string, string> = {
	aikido: "https://app.aikido.dev/api/public/v1",
	aws: "https://securityhub.us-east-1.amazonaws.com",
	checkmarx: "https://us.ast.checkmarx.net/api",
	crowdstrike: "https://api.crowdstrike.com",
	datadog: "https://api.datadoghq.com/api/v2",
	github: "https://api.github.com",
	gitlab: "https://gitlab.com/api/v4",
	jamf: "https://acme.jamfcloud.com/api",
	jira: "https://acme.atlassian.net/rest/api/3",
	mend: "https://api-saas.mend.io/api/v3.0",
	"microsoft-defender": "https://api.securitycenter.microsoft.com/api",
	"microsoft-entra": "https://graph.microsoft.com/v1.0",
	okta: "https://acme.okta.com/api/v1",
	orca: "https://api.orcasecurity.io/api",
	qualys: "https://qualysapi.qualys.com",
	rapid7: "https://us.api.insight.rapid7.com/vm/v4",
	semgrep: "https://semgrep.dev/api/v1",
	sentinelone: "https://usea1-acme.sentinelone.net/web/api/v2.1",
	servicenow: "https://acme.service-now.com/api/now",
	snyk: "https://api.snyk.io/rest",
	sonarqube: "https://sonarqube.acme.internal/api",
	tanium: "https://acme-api.cloud.tanium.com/plugin/products/gateway",
	tenable: "https://cloud.tenable.com",
	upwind: "https://api.upwind.io/v1",
	wiz: "https://api.us17.app.wiz.io/graphql",
};

const VENDOR_PATHS: Record<string, Partial<Record<ModelKey, string>>> = {
	crowdstrike: {
		detections: "/alerts/queries/alerts/v2?filter=updated_timestamp:>'{since}'",
		devices: "/devices/queries/devices-scroll/v1?limit=5000",
		vulnerabilities:
			"/spotlight/combined/vulnerabilities/v1?filter=updated_timestamp:>'{since}'&limit=400",
	},
	okta: {
		groups: "/groups?limit=200",
		users: '/users?search=lastUpdated gt "{since}"&limit=200',
	},
	qualys: {
		devices: "/qps/rest/2.0/search/am/hostasset",
		vulnerabilities:
			"/api/4.0/fo/asset/host/vm/detection/?action=list&vm_processed_after={since}&truncation_limit=1000",
	},
	snyk: {
		"code-findings":
			"/orgs/{org}/issues?version=2024-10-15&updated_after={since}",
		repositories: "/orgs/{org}/projects?version=2024-10-15",
	},
	tenable: { devices: "/assets/export", vulnerabilities: "/vulns/export" },
	wiz: {
		"cloud-findings": " (query: issuesV2)",
		"cloud-resources": " (query: cloudResources)",
		vulnerabilities: " (query: vulnerabilityFindings)",
	},
};

function vendorUrl(provider: string, model: ModelKey, since: string): string {
	const host = VENDOR_HOSTS[provider] ?? "https://api.vendor.example";
	const path =
		VENDOR_PATHS[provider]?.[model] ?? `/${model}?updated_since={since}`;
	return `${host}${path.replace("{since}", since).replace("{org}", "6d5e3c3a")}`;
}

function http(
	rng: Rng,
	at: number,
	method: string,
	url: string,
	status = 200
): LogMessage {
	const ms = rng.int(80, 1400);
	return {
		at,
		http: { method, ms, status, url },
		level: "http",
		text: `${method} ${url}`,
	};
}

function syncMessages(op: Operation, env: Environment, rng: Rng): LogMessage[] {
	const provider = op.provider ?? "";
	const integration = env.integrations.find((i) => i.id === op.integrationId);
	const models = integration?.models ?? getProvider(provider)?.models ?? [];
	const since = new Date(op.startedAt - 3_600_000).toISOString();
	let t = op.startedAt;
	const step = Math.max(
		50,
		Math.floor(op.durationMs / (models.length * 4 + 4))
	);
	const out: LogMessage[] = [
		{
			at: t,
			level: "info",
			text: `Sync job started (${op.action === "sync.initial" ? "INITIAL" : "SCHEDULED"}) for ${models.length} models`,
		},
	];
	if (
		getProvider(provider)?.auth === "CLIENT_CREDENTIALS" ||
		getProvider(provider)?.auth === "OAUTH2"
	) {
		t += step;
		out.push(
			http(rng, t, "POST", `${VENDOR_HOSTS[provider] ?? ""}/oauth2/token`)
		);
	}
	if (op.status === "failed") {
		t += step;
		out.push(
			http(
				rng,
				t,
				"GET",
				vendorUrl(provider, models[0] ?? "vulnerabilities", since),
				401
			)
		);
		out.push({
			at: t + 20,
			level: "error",
			text: '401 Unauthorized: {"errors":[{"code":401,"message":"access denied, invalid bearer token"}]}',
		});
		out.push({
			at: t + 40,
			level: "warn",
			text: "Health set to UNAUTHORIZED (resolution owner: customer). Previous data is still served.",
		});
		out.push({
			at: t + 60,
			level: "info",
			text: "Queued webhook connection.sync.failed",
		});
		return out;
	}
	let total = op.records ?? 0;
	for (const model of models) {
		const n = Math.max(
			0,
			Math.round(
				(total / Math.max(1, models.length)) * (0.6 + rng.next() * 0.8)
			)
		);
		total -= Math.min(total, n);
		const pages = Math.max(1, Math.ceil(n / 1000));
		for (let p = 1; p <= Math.min(pages, 2); p += 1) {
			t += step;
			out.push(
				http(
					rng,
					t,
					provider === "wiz" ? "POST" : "GET",
					vendorUrl(provider, model, since)
				)
			);
		}
		if (rng.bool(0.12)) {
			t += step;
			out.push({
				at: t,
				level: "warn",
				text: `429 Too Many Requests from vendor; backing off ${rng.int(2, 12)}s (Retry-After)`,
			});
		}
		t += step;
		const added = Math.round(n * rng.next() * 0.2);
		out.push({
			at: t,
			level: "info",
			text: `Normalized ${n.toLocaleString("en-US")} ${MODELS[model].name} records (${added} new, ${n - added} updated, ${rng.int(0, 4)} deleted)`,
		});
	}
	t += step;
	out.push({
		at: t,
		level: "info",
		text: `Checkpoint saved: updatedSince=${new Date(op.startedAt).toISOString()}`,
	});
	out.push({
		at: op.startedAt + op.durationMs,
		level: "info",
		text: `Sync finished in ${(op.durationMs / 1000).toFixed(1)}s`,
	});
	return out;
}

function apiMessages(op: Operation, env: Environment, rng: Rng): LogMessage[] {
	const t = op.startedAt;
	const code = op.statusCode ?? 200;
	const key = `${env.keys.secret.slice(0, 8)}…${env.keys.secret.slice(-4)}`;
	const out: LogMessage[] = [
		{
			at: t,
			level: "info",
			text: `${op.method ?? "GET"} ${op.path ?? ""}?limit=100`,
		},
		{ at: t + 2, level: "info", text: `Authenticated with secret key ${key}` },
	];
	if (code === 401) {
		out.push({
			at: t + 3,
			level: "error",
			text: "401 invalid_api_key: the key was rotated or belongs to another environment",
		});
		return out;
	}
	out.push({
		at: t + 4,
		level: "info",
		text: `Resolved connection ${op.connectionId} (${op.integrationId})`,
	});
	if (code === 404) {
		out.push({
			at: t + 6,
			level: "error",
			text: "404 not_found: the connection doesn't support this model",
		});
	} else if (code === 422) {
		out.push({
			at: t + 6,
			level: "error",
			text: '422 validation_error: "updatedSince" cannot be combined with "cursor"',
		});
	} else if (code === 429) {
		out.push({
			at: t + 6,
			level: "warn",
			text: "429 rate_limited: 100 requests per second per key",
		});
	} else if (code === 400) {
		out.push({
			at: t + 6,
			level: "error",
			text: '400 bad_request: unknown value "urgent" for "severity"',
		});
	} else {
		out.push({
			at: t + rng.int(8, 30),
			level: "info",
			text: `Served ${op.records ?? 0} records from the synced store (last sync ${rng.int(2, 55)}m ago)`,
		});
	}
	out.push({
		at: t + op.durationMs,
		level: code < 400 ? "info" : "warn",
		text: `← ${code} in ${op.durationMs}ms`,
	});
	return out;
}

function authMessages(op: Operation, rng: Rng): LogMessage[] {
	const t = op.startedAt;
	const provider = op.provider ?? "";
	const name = getProvider(provider)?.name ?? "vendor";
	if (op.action.startsWith("connect_session")) {
		return [
			{
				at: t,
				level: "info",
				text: "Connect session created, expires in 30 minutes",
			},
		];
	}
	if (op.action.includes("sandbox")) {
		return [
			{
				at: t,
				level: "info",
				text: "Sandbox connection requested; skipping credential validation",
			},
			{
				at: t + 80,
				level: "info",
				text: `Provisioned sandbox ${name} tenant for sandbox.securefabric.dev`,
			},
			{
				at: t + op.durationMs,
				level: "info",
				text: "Connection created; initial sync queued",
			},
		];
	}
	if (op.action === "connection.unauthorized") {
		return [
			http(rng, t, "GET", `${VENDOR_HOSTS[provider] ?? ""}/health`, 401),
			{
				at: t + 30,
				level: "error",
				text: `${name} rejected the stored credentials. Revoked, expired, or missing a permission.`,
			},
			{
				at: t + 50,
				level: "info",
				text: "Queued webhook connection.sync.unauthorized",
			},
		];
	}
	if (op.action === "connection.deleted") {
		return [
			{
				at: t,
				level: "info",
				text: "Credentials destroyed; scheduled syncs cancelled. Records purge in 31 days.",
			},
		];
	}
	if (op.status === "failed") {
		return [
			{
				at: t,
				level: "error",
				text: `${name} returned 401 during validation. Nothing was stored.`,
			},
		];
	}
	return [
		{
			at: t,
			level: "info",
			text: "Credentials received from SecureFabric Connect",
		},
		http(rng, t + 200, "GET", `${VENDOR_HOSTS[provider] ?? ""}/whoami`),
		{
			at: t + 900,
			level: "info",
			text: "Permissions check passed for all requested scopes",
		},
		{
			at: t + 1100,
			level: "info",
			text: "Credentials encrypted (AES-256-GCM) and stored",
		},
		{
			at: t + op.durationMs,
			level: "info",
			text: "Connection created; initial sync queued",
		},
	];
}

function webhookMessages(
	op: Operation,
	env: Environment,
	rng: Rng
): LogMessage[] {
	const url = op.path ?? env.webhooks[0]?.url ?? "https://example.com/webhooks";
	const t = op.startedAt;
	return [
		{
			at: t,
			level: "info",
			text: `Event ${op.action.replace("webhook.", "")} for ${op.connectionId ?? "environment"}`,
		},
		{
			at: t + 1,
			level: "info",
			text: `X-SecureFabric-Signature: t=${Math.floor(t / 1000)},v1=${rng.hex(64)}`,
		},
		http(rng, t + 2, "POST", url, op.statusCode ?? 200),
		{ at: t + op.durationMs, level: "info", text: "Delivered on attempt 1" },
	];
}

function proxyMessages(op: Operation, rng: Rng): LogMessage[] {
	const provider = op.provider ?? "";
	const t = op.startedAt;
	return [
		{
			at: t,
			level: "info",
			text: `Passthrough to ${getProvider(provider)?.name ?? provider}`,
		},
		{
			at: t + 3,
			level: "info",
			text: "Injected stored credentials (token refreshed 14m ago)",
		},
		http(
			rng,
			t + 5,
			"GET",
			`${VENDOR_HOSTS[provider] ?? ""}/${provider === "tenable" ? "plugins/plugin/19506" : "v1/raw"}`,
			op.status === "failed" ? 502 : 200
		),
		{
			at: t + op.durationMs,
			level: op.status === "failed" ? "error" : "info",
			text:
				op.status === "failed"
					? "← 502 vendor_error"
					: `← 200 in ${op.durationMs}ms`,
		},
	];
}

function actionMessages(op: Operation, rng: Rng): LogMessage[] {
	const provider = op.provider ?? "";
	const t = op.startedAt;
	const failed = op.status === "failed";
	return [
		{
			at: t,
			level: "info",
			text: `${op.method} ${op.path}: accepted (202), idempotency key incident-${rng.int(100, 999)}`,
		},
		http(
			rng,
			t + 200,
			"POST",
			`${VENDOR_HOSTS[provider] ?? ""}/devices/entities/devices-actions/v2?action_name=contain`,
			failed ? 403 : 202
		),
		{
			at: t + op.durationMs,
			level: failed ? "error" : "info",
			text: failed
				? "Vendor refused: missing Hosts: Write permission. Sent action.failed"
				: "Vendor confirmed. Sent action.completed",
		},
	];
}

export function operationMessages(
	op: Operation,
	env: Environment
): LogMessage[] {
	const rng = createRng(op.id);
	switch (op.type) {
		case "sync":
			return syncMessages(op, env, rng);
		case "api":
			return apiMessages(op, env, rng);
		case "auth":
			return authMessages(op, rng);
		case "webhook":
			return webhookMessages(op, env, rng);
		case "proxy":
			return proxyMessages(op, rng);
		case "action":
			return actionMessages(op, rng);
		default:
			return [];
	}
}
