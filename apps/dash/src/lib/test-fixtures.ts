import type { Connection, Environment } from "./types";

/** A small environment in the API's shape, for unit tests (the real one comes
 * from `GET /api/v1/workspace`, seeded by `packages/domain`). */
export function fixtureEnvironment(now: number): Environment {
	const connection = (
		id: string,
		provider: string,
		counts: Connection["counts"]
	): Connection => ({
		counts,
		createdAt: now - 86_400_000 * 30,
		credentials: {},
		customer: {
			email: "secops@globex.io",
			endUserId: "org_globex",
			orgName: "Globex",
		},
		domain: "globex.io",
		frequencyOverride: null,
		health: "HEALTHY",
		id,
		integrationId: provider,
		jobs: [],
		lastSyncAt: now - 600_000,
		metadata: {},
		paused: false,
		provider,
		sandbox: false,
		tags: { end_user_email: "secops@globex.io" },
		webhookOverride: null,
	});
	return {
		apiKeys: [],
		callbackUrl: "https://api.securefabric.dev/v1/connect/callback",
		connect: { brandName: "Acme Security", hideBadge: false, theme: "system" },
		connections: [
			connection("conn_tenable000001", "tenable", {
				devices: 320,
				vulnerabilities: 2400,
			}),
			connection("conn_okta000000001", "okta", { groups: 12, users: 400 }),
		],
		createdAt: now - 86_400_000 * 90,
		id: "env_fixture01",
		integrations: [],
		isProduction: false,
		keys: { rotatedAt: now, secret: "sk_test_fixture" },
		name: "Development",
		operations: [],
		slug: "dev",
		variables: [],
		webhookSecret: "whsec_fixture",
		webhooks: [],
	};
}
