/**
 * The API's wire format, modelled on Leen's unified API
 * v1 (docs.leen.dev): snake_case fields, lowercase enums, the vendor named in
 * `vendor`, and the vendor's own record under `vendor_data`. Like v1, alert
 * verdicts stay upper-case (FALSE_POSITIVE, TRUE_POSITIVE).
 *
 * Records are generated in a friendlier camelCase shape (lib/records.ts) and
 * converted here, at the edge, so the playground, the records explorer and
 * the code samples all show exactly what the API returns.
 */

import type { ModelKey } from "./catalog";
import type { Json, JsonObject, MockRecord } from "./records";

const UPPER = /[A-Z]/gu;
const IDENTIFIER = /^[A-Za-z][A-Za-z0-9_]*$/u;

/** Fields whose values are enums, lowercased on the wire. */
const ENUM_FIELDS = new Set([
	"cloud",
	"health",
	"platform",
	"priority",
	"severity",
	"state",
	"status",
	"type",
]);

/** Vulnerability lifecycle, in Leen's `state` vocabulary. */
const VULNERABILITY_STATE: Record<string, string> = {
	accepted: "ignored",
	fixed: "closed",
	open: "open",
	reopened: "reopened",
};

/** Code finding types, in Leen's vocabulary. */
const CODE_FINDING_TYPE: Record<string, string> = {
	iac: "iac",
	sast: "code",
	sca: "dependency",
	secret: "secret",
};

export function snakeCase(key: string): string {
	return key.replace(UPPER, (ch) => `_${ch.toLowerCase()}`);
}

/** Leen v1's vendor enum: lowercase snake_case, e.g. `crowdstrike`. */
export function vendorCode(provider: string): string {
	return provider.toLowerCase().replaceAll("-", "_");
}

function convert(value: Json, key: string): Json {
	if (Array.isArray(value)) {
		return value.map((v) => convert(v, key));
	}
	if (value && typeof value === "object") {
		const out: JsonObject = {};
		for (const [k, v] of Object.entries(value)) {
			out[snakeCase(k)] = convert(v, k);
		}
		return out;
	}
	if (
		typeof value === "string" &&
		ENUM_FIELDS.has(key) &&
		IDENTIFIER.test(value)
	) {
		return value.toLowerCase();
	}
	return value;
}

function reshapeVulnerability(u: JsonObject): JsonObject {
	const { asset, cve, cvss, package: pkg, solution, status, ...rest } = u;
	const score = cvss as JsonObject | undefined;
	const host = asset as JsonObject | undefined;
	const fixedIn = (pkg as JsonObject | undefined)?.fixedIn;
	return {
		...rest,
		cve: Array.isArray(cve) ? cve : [],
		cvssBaseScore: score?.score ?? null,
		cvssVersion: score?.version ?? null,
		device: host
			? {
					hostnames: host.hostname ? [host.hostname] : [],
					id: host.id ?? null,
					ipv4s: host.ip ? [host.ip] : [],
				}
			: null,
		package: pkg ?? null,
		patchable: Boolean(fixedIn),
		solution: solution ?? null,
		state: VULNERABILITY_STATE[String(status)] ?? "open",
	};
}

/** Device agent states, in Leen's device `status` vocabulary. */
const DEVICE_STATUS: Record<string, string> = {
	isolated: "quarantined",
	offline: "offline",
	online: "active",
};

/** Leen's Device: hostnames and addresses as arrays, the reporting tools
 * under source_vendors, and the signed-in users under identities. */
function reshapeDevice(u: JsonObject): JsonObject {
	const { agent, hostname, lastUser, status, vendor, vendorId, ...rest } = u;
	const info = (agent ?? {}) as JsonObject;
	return {
		...rest,
		hostnames: hostname ? [hostname] : [],
		identities: lastUser ? [{ username: lastUser }] : [],
		sourceVendors: [
			{
				agentInfo: {
					agentHealth: info.health ?? null,
					agentVersion: info.version ?? null,
				},
				vendor: vendor ?? null,
				vendorId: vendorId ?? u.id ?? null,
			},
		],
		status: DEVICE_STATUS[String(status)] ?? "unknown",
	};
}

/** Leen's EDR alert: event times, flat process fields, MITRE tactics with
 * their techniques nested. */
function reshapeDetection(u: JsonObject): JsonObject {
	const { firstEventAt, lastEventAt, mitre, process, user, verdict, ...rest } =
		u;
	const proc = (process ?? {}) as JsonObject;
	return {
		...rest,
		firstEventTime: firstEventAt ?? null,
		lastEventTime: lastEventAt ?? null,
		mitre: Array.isArray(mitre)
			? mitre.map((m) => {
					const t = m as JsonObject;
					return {
						tacticId: t.tacticId ?? null,
						tacticName: t.tactic ?? null,
						techniques: [
							{
								techniqueId: t.techniqueId ?? null,
								techniqueLink: t.techniqueId
									? `https://attack.mitre.org/techniques/${String(t.techniqueId).replace(".", "/")}/`
									: null,
								techniqueName: t.technique ?? null,
							},
						],
					};
				})
			: [],
		processCommandLine: proc.commandLine ?? null,
		processFilename: proc.name ?? null,
		processSha256: proc.sha256 ?? null,
		userName: user ?? null,
		verdict: typeof verdict === "string" ? verdict.toUpperCase() : "UNKNOWN",
	};
}

/** Leen's IDP user: email_addr, full_name, flat MFA and admin flags, and the
 * vendor's own account status as text (Okta's is upper-case: ACTIVE). */
function reshapeUser(u: JsonObject): JsonObject {
	const { createdAt, email, mfa, name, status, title, ...rest } = u;
	const factors = (mfa ?? {}) as JsonObject;
	const handle = typeof email === "string" ? email.split("@")[0] : null;
	return {
		...rest,
		emailAddr: email ?? null,
		fullName: name ?? null,
		isDeleted: status === "deprovisioned",
		isMfaEnabled: factors.enabled ?? false,
		jobTitle: title ?? null,
		mfaFactors: factors.factors ?? [],
		name: handle,
		vendorCreatedAt: createdAt ?? null,
		vendorStatus: typeof status === "string" ? status.toUpperCase() : null,
	};
}

/** Leen's ITSM ticket: name, the vendor's key as identifier, and the
 * vendor's own status and priority text. */
function reshapeTicket(u: JsonObject): JsonObject {
	const { assignee, createdAt, key, title, ...rest } = u;
	return {
		...rest,
		active: rest.status !== "done",
		assignedUser: assignee ?? null,
		identifier: key ?? null,
		name: title ?? null,
		ticketCreatedAt: createdAt ?? null,
	};
}

const RESHAPERS: Partial<Record<ModelKey, (u: JsonObject) => JsonObject>> = {
	detections: reshapeDetection,
	devices: reshapeDevice,
	tickets: reshapeTicket,
	users: reshapeUser,
	vulnerabilities: reshapeVulnerability,
};

function reshape(model: ModelKey, u: JsonObject): JsonObject {
	const { source, sourceId, ...rest } = u;
	const base: JsonObject = {
		...rest,
		...(source === undefined ? {} : { vendor: vendorCode(String(source)) }),
		...(sourceId === undefined ? {} : { vendorId: sourceId }),
	};
	const reshaper = RESHAPERS[model];
	if (reshaper) {
		return reshaper(base);
	}
	if (model === "code-findings" && typeof base.type === "string") {
		return { ...base, type: CODE_FINDING_TYPE[base.type] ?? base.type };
	}
	return base;
}

/** `id` first, then the rest alphabetically, as API references list them. */
function ordered(r: JsonObject): JsonObject {
	const { id, ...rest } = r;
	const out: JsonObject = id === undefined ? {} : { id };
	for (const key of Object.keys(rest).sort()) {
		out[key] = rest[key] as Json;
	}
	return out;
}

/** One record as the API returns it. */
export function toWire(
	model: ModelKey,
	record: MockRecord,
	{ vendorData = true }: { vendorData?: boolean } = {}
): JsonObject {
	const out = ordered(
		convert(reshape(model, record.unified), "") as JsonObject
	);
	if (!vendorData) {
		return out;
	}
	return {
		...out,
		vendor_data: {
			vendor:
				typeof record.unified.source === "string"
					? vendorCode(record.unified.source)
					: null,
			...record.raw,
		},
	};
}

/** Wire value of a field, for filtering on query params. */
export function wireField(r: JsonObject, param: string): Json | undefined {
	if (param === "mfaEnabled") {
		return r.is_mfa_enabled;
	}
	return r[snakeCase(param)];
}

/** Leen's v2 error body. */
export function errorBody(
	status: number,
	code: string,
	message: string,
	detail: JsonObject[] = []
): JsonObject {
	let type = "invalid_request_error";
	if (status === 401 || status === 403) {
		type = "authorization_error";
	} else if (status >= 500) {
		type = "api_error";
	}
	return { code, detail, message, type };
}
