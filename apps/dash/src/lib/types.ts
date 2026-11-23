import type { schemas } from "@securefabric/client";
import type { ModelKey } from "./catalog";

/*
 * The domain the dash renders. Every shape below is the API's: derived from the
 * OpenAPI schema (`@securefabric/client`), which FastAPI builds from the
 * pydantic models in `packages/domain`. Change a field there, run
 * `make generate`, and the dash stops typechecking until it catches up.
 */

type Api = schemas;

export type SyncFrequency = Api["Integration"]["syncFrequency"];

export const FREQUENCY_LABELS: Record<SyncFrequency, string> = {
	"1h": "Every hour",
	"4h": "Every 4 hours",
	"12h": "Every 12 hours",
	"15m": "Every 15 minutes",
	"24h": "Daily",
};

export const FREQUENCY_MS: Record<SyncFrequency, number> = {
	"1h": 3_600_000,
	"4h": 14_400_000,
	"12h": 43_200_000,
	"15m": 900_000,
	"24h": 86_400_000,
};

export type Integration = Api["Integration"];

/** Health codes follow the connection-health model: who has to act, and why. */
export type HealthCode = Api["Connection"]["health"];

export interface HealthInfo {
	description: string;
	label: string;
	owner: "SecureFabric" | "Customer" | "Vendor" | "You";
	tone: "ok" | "warn" | "error" | "neutral" | "busy";
}

export const HEALTH: Record<HealthCode, HealthInfo> = {
	EXECUTION_TIMEOUT: {
		description:
			"The last sync ran past its timeout. SecureFabric retries with smaller pages automatically.",
		label: "Timed out",
		owner: "SecureFabric",
		tone: "warn",
	},
	HEALTHY: {
		description: "The last sync succeeded and credentials are valid.",
		label: "Healthy",
		owner: "SecureFabric",
		tone: "ok",
	},
	PAUSED: {
		description:
			"Scheduled syncs are paused. API reads return the last synced data.",
		label: "Paused",
		owner: "You",
		tone: "neutral",
	},
	RATE_LIMIT_EXCEEDED: {
		description:
			"The vendor returned 429s. SecureFabric backs off and resumes on the next window.",
		label: "Rate limited",
		owner: "SecureFabric",
		tone: "warn",
	},
	SYNCING: {
		description: "A sync is running. Records appear as each model finishes.",
		label: "Syncing",
		owner: "SecureFabric",
		tone: "busy",
	},
	UNAUTHORIZED: {
		description:
			"The vendor rejected the stored credentials. They were revoked, expired or lack a permission. Send the customer a reconnect link.",
		label: "Unauthorized",
		owner: "Customer",
		tone: "error",
	},
	VENDOR_SERVER_ERROR: {
		description:
			"The vendor's API returned 5xx errors. SecureFabric retries with backoff.",
		label: "Vendor error",
		owner: "Vendor",
		tone: "warn",
	},
};

export type SyncJob = Api["SyncJob"];
export type JobStatus = SyncJob["status"];
export type JobType = SyncJob["type"];
export type Customer = Api["Customer"];

/** Record counts are keyed by model; the wire format is a plain string map. */
export type Connection = Omit<Api["Connection"], "counts"> & {
	counts: Partial<Record<ModelKey, number>>;
};

export type Operation = Api["Operation"];
export type OperationType = Operation["type"];
export type OperationStatus = Operation["status"];

export const WEBHOOK_EVENTS = [
	"connection.create.succeeded",
	"connection.create.failed",
	"connection.sync.succeeded",
	"connection.sync.failed",
	"connection.sync.unauthorized",
	"connection.deleted",
	"action.completed",
	"action.failed",
] as const;

export type WebhookEvent = (typeof WEBHOOK_EVENTS)[number];
export type Webhook = Api["Webhook"];
export type EnvVariable = Api["EnvVariable"];
export type ConnectTheme = Api["ConnectSettings"]["theme"];

export type Environment = Omit<Api["Environment"], "connections"> & {
	connections: Connection[];
};

export type Role = Api["Member"]["role"];

/**
 * What a key may do. Keys belong to one environment and only see its
 * connections; scopes narrow them further, so a reporting job can read data
 * without being able to delete a connection.
 */
export const KEY_SCOPES = [
	"data:read",
	"actions:write",
	"connections:write",
	"integrations:write",
	"webhooks:write",
	"keys:write",
] as const;

export type KeyScope = (typeof KEY_SCOPES)[number];

/** An API key. Only a preview is kept; the full key is shown once. The
 * default key's value is what the dash's samples and playground use; it can be
 * rolled but not revoked. */
export type ApiKey = Api["ApiKey"];
export type Member = Api["Member"];

export type Workspace = Omit<Api["Workspace"], "environments"> & {
	environments: Environment[];
};

// The lists the UI iterates must match the API's enums exactly, both ways.
type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
type Expect<T extends true> = T;
export type ContractChecks = [
	Expect<Same<WebhookEvent, Api["Webhook"]["events"][number]>>,
	Expect<Same<KeyScope, ApiKey["scopes"][number]>>,
	Expect<Same<ModelKey, Integration["models"][number]>>,
];
