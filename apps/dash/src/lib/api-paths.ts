import type { ModelKey } from "./catalog";

/** The unified API's list route for each model (most are just `/v1/<model>`). */
const API_PATHS: Partial<Record<ModelKey, string>> = {
	alerts: "/v1/alerts",
	"cloud-findings": "/v1/cloud-findings",
	"cloud-resources": "/v1/cloud-resources",
	"code-findings": "/v1/code-findings",
	detections: "/v1/detections",
	devices: "/v1/devices",
	groups: "/v1/groups",
	repositories: "/v1/repositories",
	tickets: "/v1/tickets",
	users: "/v1/users",
	vulnerabilities: "/v1/vulnerabilities",
};

export function apiPath(model: ModelKey): string {
	return API_PATHS[model] ?? `/v1/${model}`;
}
