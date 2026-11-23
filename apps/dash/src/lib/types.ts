import type { operations, schemas } from "@securefabric/client";
import type { Tone } from "@/components/ui/primitives";

/*
 * The domain the dash renders. Every shape is the API's, from the OpenAPI
 * document through `@securefabric/client`: change a field in the API, run
 * `make generate`, and the dash stops typechecking until it catches up.
 */

export type Me = schemas["Me"];
export type Environment = schemas["EnvironmentOut"];
export type Connector = schemas["ConnectorOut"];
export type Integration = schemas["IntegrationOut"];
export type VendorApp = schemas["VendorAppOut"];
export type Organization = schemas["OrganizationOut"];
export type Connection = schemas["ConnectionOut"];
export type StreamStatus = schemas["StreamStatus"];
export type Health = schemas["HealthOut"];
export type Job = schemas["JobOut"];
export type StreamRun = schemas["StreamRunOut"];
export type Finding = schemas["FindingOut"];
export type Resource = schemas["ResourceOut"];
export type Operation = schemas["OperationOut"];
export type WebhookEndpoint = schemas["EndpointOut"];
export type Delivery = schemas["DeliveryOut"];
export type ApiKey = schemas["ApiKeyOut"];
export type Member = schemas["MemberOut"];
export type Usage = schemas["Usage"];
export type Alert = schemas["AlertOut"];
export type RepairTask = schemas["RepairTask"];
/** trigger, pause, resume, reset, renormalize, purge_now, rebuild_counts, reprobe. */
export type RepairAction =
	operations["admin:admin_repair"]["parameters"]["path"]["action"];

export interface HealthInfo {
	label: string;
	owner: string;
	tone: Tone;
}

/** Health codes (part 3, section 7): who has to act, and why. */
export const HEALTH: Record<string, HealthInfo> = {
	CONFIGURATION_ERROR: {
		label: "Configuration error",
		owner: "Customer",
		tone: "error",
	},
	EXECUTION_TIMEOUT: {
		label: "Timed out",
		owner: "SecureFabric",
		tone: "warn",
	},
	HEALTHY: { label: "Healthy", owner: "", tone: "ok" },
	INITIALIZING: { label: "Initializing", owner: "SecureFabric", tone: "busy" },
	INTERNAL_ERROR: {
		label: "Internal error",
		owner: "SecureFabric",
		tone: "error",
	},
	RATE_LIMIT_EXCEEDED: { label: "Rate limited", owner: "Vendor", tone: "warn" },
	REAUTHORIZATION_REQUIRED: {
		label: "Re-authorize",
		owner: "Customer",
		tone: "error",
	},
	UNAUTHORIZED: { label: "Unauthorized", owner: "Customer", tone: "error" },
	VENDOR_CLIENT_ERROR: {
		label: "Vendor client error",
		owner: "Customer",
		tone: "error",
	},
	VENDOR_SERVER_ERROR: {
		label: "Vendor server error",
		owner: "Vendor",
		tone: "warn",
	},
};

export function healthInfo(code: string): HealthInfo {
	return HEALTH[code] ?? { label: code, owner: "", tone: "neutral" };
}

export const STATE_TONES: Record<string, Tone> = {
	ACTIVE: "ok",
	DELETED: "neutral",
	HARD_DELETED: "neutral",
	PAUSED: "warn",
	PENDING: "busy",
};

export const SEVERITIES = [
	"CRITICAL",
	"HIGH",
	"MEDIUM",
	"LOW",
	"INFO",
	"UNKNOWN",
] as const;
export const FINDING_STATES = [
	"OPEN",
	"REOPENED",
	"CLOSED",
	"IGNORED",
	"DELETED",
	"UNKNOWN",
] as const;
export const FINDING_TYPES = [
	"DEPENDENCY",
	"CODE",
	"SECRET",
	"CONTAINER",
	"IAC",
	"HOST",
	"DOMAIN",
	"UNKNOWN",
] as const;
export const RESOURCE_TYPES = [
	"REPOSITORY",
	"BRANCH",
	"HOST",
	"CONTAINER",
	"IMAGE",
	"DEPENDENCY",
	"KUBERNETES",
	"VENDOR",
	"FUNCTION",
	"SOFTWARE",
	"UNKNOWN",
] as const;

export const JOB_TONES: Record<string, Tone> = {
	CANCELLED: "neutral",
	FAILED: "error",
	PARTIAL: "warn",
	QUEUED: "busy",
	RUNNING: "busy",
	SUCCESS: "ok",
};

export const RUN_TONES: Record<string, Tone> = {
	ADMITTED: "busy",
	CANCELLED: "neutral",
	EXPIRED: "warn",
	FAILED: "error",
	PARKED: "warn",
	QUEUED: "busy",
	RETRY_WAIT: "warn",
	RUNNING: "busy",
	SUCCEEDED: "ok",
};

export const GRANT_TONES: Record<string, Tone> = {
	GRANTED: "ok",
	NOT_ENABLED: "neutral",
	UNAUTHORIZED: "error",
	UNKNOWN: "warn",
	UNSUPPORTED: "neutral",
};

/** Logos shipped in public/integrations, keyed by connector id. */
export const CONNECTOR_LOGOS: Record<string, string> = {
	GITHUB: "/integrations/github.svg",
	SANDBOX: "/icon.svg",
};

export const FINDING_STATE_TONES: Record<string, Tone> = {
	CLOSED: "ok",
	DELETED: "neutral",
	IGNORED: "neutral",
	OPEN: "error",
	REOPENED: "warn",
	UNKNOWN: "neutral",
};

export const OP_TONES: Record<string, Tone> = {
	cancelled: "neutral",
	failed: "error",
	running: "busy",
	success: "ok",
	warning: "warn",
};

export const DELIVERY_TONES: Record<string, Tone> = {
	DEAD: "error",
	DELIVERED: "ok",
	FAILED: "warn",
	PENDING: "busy",
};
