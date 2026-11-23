"use client";

/**
 * The dash's state: the workspace snapshot from `GET /api/v1/workspace`, read
 * through useSyncExternalStore.
 *
 * The backend owns everything (Postgres, `packages/domain`). Actions call the
 * typed API client, patch the local snapshot optimistically where the outcome
 * is obvious, then refetch. Syncs are durable tasks the worker finishes, so the
 * store polls fast while any job is running and slowly otherwise.
 */

import { type RequestBody, unwrap } from "@securefabric/client";
import { useSyncExternalStore } from "react";
import { toast } from "sonner";
import { api } from "./api";
import type {
	ApiKey,
	Connection,
	Customer,
	Environment,
	HealthCode,
	Integration,
	KeyScope,
	Operation,
	Role,
	Webhook,
	WebhookEvent,
	Workspace,
} from "./types";

const FAST_POLL_MS = 1000;
const IDLE_POLL_MS = 10_000;
const MAX_OPERATIONS = 800;

export type LoadState =
	| { status: "loading" }
	| { status: "ready" }
	| { error: string; status: "offline" };

let state: Workspace | null = null;
let load: LoadState = { status: "loading" };
const listeners = new Set<() => void>();

function emit(): void {
	for (const l of listeners) {
		l();
	}
}

function setState(next: Workspace): void {
	state = next;
	load = { status: "ready" };
	emit();
}

/** Apply an optimistic patch; the next refetch replaces it with the truth. */
function patch(update: (ws: Workspace) => Workspace): void {
	if (state) {
		setState(update(state));
	}
}

// --- Fetching and polling ------------------------------------------------------

let inflight: Promise<void> | null = null;

export function refresh(): Promise<void> {
	inflight ??= unwrap(api.GET("/api/v1/workspace"))
		.then((ws) => setState(ws as Workspace))
		.catch((error: unknown) => {
			load = {
				error:
					error instanceof Error ? error.message : "The API is unreachable",
				status: "offline",
			};
			emit();
		})
		.finally(() => {
			inflight = null;
		});
	return inflight;
}

function isBusy(ws: Workspace | null): boolean {
	return Boolean(
		ws?.environments.some((env) =>
			env.connections.some(
				(c) => c.health === "SYNCING" || c.jobs[0]?.status === "RUNNING"
			)
		)
	);
}

let pollTimer: ReturnType<typeof setTimeout> | undefined;

function schedulePoll(): void {
	clearTimeout(pollTimer);
	if (listeners.size === 0) {
		return;
	}
	const delay =
		isBusy(state) || load.status === "offline" ? FAST_POLL_MS : IDLE_POLL_MS;
	pollTimer = setTimeout(async () => {
		if (document.visibilityState === "visible") {
			await refresh();
		}
		schedulePoll();
	}, delay);
}

let refreshTimer: ReturnType<typeof setTimeout> | undefined;

/** Coalesce bursts (live traffic logging several requests) into one refetch. */
function refreshSoon(ms = 800): void {
	clearTimeout(refreshTimer);
	refreshTimer = setTimeout(() => {
		refresh().then(schedulePoll);
	}, ms);
}

function onVisible(): void {
	if (document.visibilityState === "visible") {
		refresh().then(schedulePoll);
	}
}

function subscribe(listener: () => void): () => void {
	listeners.add(listener);
	if (listeners.size === 1) {
		document.addEventListener("visibilitychange", onVisible);
		refresh().then(schedulePoll);
	}
	return () => {
		listeners.delete(listener);
		if (listeners.size === 0) {
			clearTimeout(pollTimer);
			document.removeEventListener("visibilitychange", onVisible);
		}
	};
}

const getSnapshot = (): Workspace | null => state;
const getServerSnapshot = (): Workspace | null => null;
const getLoadState = (): LoadState => load;
const LOADING: LoadState = { status: "loading" };
const getServerLoadState = (): LoadState => LOADING;

/** The current workspace outside React (null until the first fetch lands). */
export function readWorkspace(): Workspace | null {
	return state;
}

/** The workspace, or null while loading, during server render, or offline. */
export function useWorkspace(): Workspace | null {
	return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/** Whether the snapshot is loading, ready, or the API can't be reached. */
export function useLoadState(): LoadState {
	return useSyncExternalStore(subscribe, getLoadState, getServerLoadState);
}

// --- Mutations -------------------------------------------------------------------

/**
 * Run a request, then refetch. Failures are toasted and roll the optimistic
 * patch back (the refetch restores the server's state).
 */
async function mutate<T>(
	request: () => Promise<T>,
	optimistic?: (ws: Workspace) => Workspace
): Promise<T> {
	if (optimistic) {
		patch(optimistic);
	}
	try {
		const result = await request();
		await refresh();
		schedulePoll();
		return result;
	} catch (error) {
		toast.error(error instanceof Error ? error.message : "Request failed");
		await refresh();
		throw error;
	}
}

/** For fire-and-forget actions: the toast already reported the failure. */
function run(
	request: () => Promise<unknown>,
	optimistic?: (ws: Workspace) => Workspace
): Promise<void> {
	return mutate(request, optimistic).then(
		() => undefined,
		() => undefined
	);
}

function mapEnv(
	slug: string,
	update: (env: Environment) => Environment
): (ws: Workspace) => Workspace {
	return (ws) => ({
		...ws,
		environments: ws.environments.map((e) => (e.slug === slug ? update(e) : e)),
	});
}

function mapConnection(
	slug: string,
	id: string,
	update: (c: Connection) => Connection
): (ws: Workspace) => Workspace {
	return mapEnv(slug, (env) => ({
		...env,
		connections: env.connections.map((c) => (c.id === id ? update(c) : c)),
	}));
}

const envPath = (slug: string) => ({ params: { path: { env: slug } } });

// --- Operations (logs) ---------------------------------------------------------

type NewOperation = Pick<
	Operation,
	"action" | "durationMs" | "status" | "type"
> &
	Partial<
		Pick<Operation, "method" | "path" | "records" | "startedAt" | "statusCode">
	>;

/**
 * Log a request made from the dash (the playground, live traffic). Shown at
 * once, then persisted; bursts share one refetch.
 */
export function logOperation(
	slug: string,
	connectionId: string | null,
	op: NewOperation
): void {
	const startedAt = op.startedAt ?? Date.now();
	patch(
		mapEnv(slug, (e) => {
			const conn = e.connections.find((c) => c.id === connectionId);
			const local: Operation = {
				connectionId,
				customer: conn?.customer.orgName ?? null,
				id: `op_local_${startedAt}_${Math.random().toString(36).slice(2, 8)}`,
				integrationId: conn?.integrationId ?? null,
				method: null,
				path: null,
				provider: conn?.provider ?? null,
				records: null,
				statusCode: null,
				...op,
				startedAt,
			};
			return {
				...e,
				operations: [local, ...e.operations].slice(0, MAX_OPERATIONS),
			};
		})
	);
	api
		.POST("/api/v1/environments/{env}/operations", {
			...envPath(slug),
			body: { ...op, connectionId, startedAt },
		})
		.then(() => refreshSoon())
		.catch(() => undefined);
}

// --- Environments ------------------------------------------------------------------

const SLUG_CHARS = /[^a-z0-9-]+/gu;

export function slugifyEnv(name: string): string {
	return name
		.trim()
		.toLowerCase()
		.replaceAll(" ", "-")
		.replace(SLUG_CHARS, "")
		.slice(0, 24);
}

/** Returns the new environment's slug (made unique by the API). */
export async function createEnvironment(input: {
	name: string;
	slug: string;
	isProduction: boolean;
	copyFrom: string | null;
}): Promise<string> {
	const created = await mutate(() =>
		unwrap(api.POST("/api/v1/environments", { body: input }))
	);
	return created.id;
}

export function updateEnvironment(
	slug: string,
	changes: RequestBody<"environments:update_environment">
): Promise<void> {
	return run(
		() =>
			unwrap(
				api.PATCH("/api/v1/environments/{env}", {
					...envPath(slug),
					body: changes,
				})
			),
		mapEnv(slug, (e) => ({
			...e,
			callbackUrl: changes.callbackUrl ?? e.callbackUrl,
			connect: {
				brandName: changes.connect?.brandName ?? e.connect.brandName,
				hideBadge: changes.connect?.hideBadge ?? e.connect.hideBadge,
				theme: changes.connect?.theme ?? e.connect.theme,
			},
			isProduction: changes.isProduction ?? e.isProduction,
			name: changes.name ?? e.name,
		}))
	);
}

export function deleteEnvironment(slug: string): Promise<void> {
	return run(
		() => unwrap(api.DELETE("/api/v1/environments/{env}", envPath(slug))),
		(ws) => ({
			...ws,
			environments: ws.environments.filter((e) => e.slug !== slug),
		})
	);
}

// --- API keys ------------------------------------------------------------------------

/** Returns the full key, which the caller shows once and never stores. */
export async function createApiKey(
	slug: string,
	name: string,
	scopes: KeyScope[]
): Promise<string> {
	const created = await mutate(() =>
		unwrap(
			api.POST("/api/v1/environments/{env}/keys", {
				...envPath(slug),
				body: { name, scopes },
			})
		)
	);
	return created.secret;
}

export function updateApiKey(
	slug: string,
	id: string,
	changes: Partial<Pick<ApiKey, "name" | "scopes">>
): Promise<void> {
	return run(
		() =>
			unwrap(
				api.PATCH("/api/v1/environments/{env}/keys/{key_id}", {
					body: changes,
					params: { path: { env: slug, key_id: id } },
				})
			),
		mapEnv(slug, (e) => ({
			...e,
			apiKeys: e.apiKeys.map((k) => (k.id === id ? { ...k, ...changes } : k)),
		}))
	);
}

/**
 * Replaces a key's value and returns the new one, shown once. Rolling the
 * default key also changes what the dashboard's samples use.
 */
export async function rollApiKey(slug: string, id: string): Promise<string> {
	const rolled = await mutate(() =>
		unwrap(
			api.POST("/api/v1/environments/{env}/keys/{key_id}/roll", {
				params: { path: { env: slug, key_id: id } },
			})
		)
	);
	return rolled.secret;
}

export function revokeApiKey(slug: string, id: string): Promise<void> {
	return run(
		() =>
			unwrap(
				api.DELETE("/api/v1/environments/{env}/keys/{key_id}", {
					params: { path: { env: slug, key_id: id } },
				})
			),
		mapEnv(slug, (e) => ({
			...e,
			apiKeys: e.apiKeys.filter((k) => k.id !== id || k.isDefault),
		}))
	);
}

// --- Webhooks and variables --------------------------------------------------------

export function rotateWebhookSecret(slug: string): Promise<void> {
	return run(() =>
		unwrap(
			api.POST(
				"/api/v1/environments/{env}/webhook-secret/rotate",
				envPath(slug)
			)
		)
	);
}

export async function addWebhook(
	slug: string,
	url: string,
	events: WebhookEvent[],
	description = ""
): Promise<string> {
	const created = await mutate(() =>
		unwrap(
			api.POST("/api/v1/environments/{env}/webhooks", {
				...envPath(slug),
				body: { description, events, url },
			})
		)
	);
	return created.id;
}

export function updateWebhook(
	slug: string,
	id: string,
	changes: Partial<Pick<Webhook, "description" | "disabled" | "events" | "url">>
): Promise<void> {
	return run(
		() =>
			unwrap(
				api.PATCH("/api/v1/environments/{env}/webhooks/{webhook_id}", {
					body: changes,
					params: { path: { env: slug, webhook_id: id } },
				})
			),
		mapEnv(slug, (e) => ({
			...e,
			webhooks: e.webhooks.map((w) => (w.id === id ? { ...w, ...changes } : w)),
		}))
	);
}

export function removeWebhook(slug: string, id: string): Promise<void> {
	return run(
		() =>
			unwrap(
				api.DELETE("/api/v1/environments/{env}/webhooks/{webhook_id}", {
					params: { path: { env: slug, webhook_id: id } },
				})
			),
		mapEnv(slug, (e) => ({
			...e,
			webhooks: e.webhooks.filter((w) => w.id !== id),
		}))
	);
}

/**
 * Delivers one event to one endpoint now: a test event from the endpoint's
 * page, or a resend of an earlier delivery. Lands in that endpoint's
 * deliveries and in Logs, like a real delivery.
 */
export function deliverWebhook(
	slug: string,
	id: string,
	event: WebhookEvent | "ping",
	connectionId: string | null = null
): Promise<void> {
	return run(() =>
		unwrap(
			api.POST("/api/v1/environments/{env}/webhooks/{webhook_id}/deliveries", {
				body: { connectionId, event },
				params: { path: { env: slug, webhook_id: id } },
			})
		)
	);
}

export function setVariable(
	slug: string,
	key: string,
	value: string,
	secret: boolean
): Promise<void> {
	return run(
		() =>
			unwrap(
				api.PUT("/api/v1/environments/{env}/variables/{key}", {
					body: { secret, value },
					params: { path: { env: slug, key } },
				})
			),
		mapEnv(slug, (e) => ({
			...e,
			variables: [
				...e.variables.filter((v) => v.key !== key),
				{ key, secret, value },
			],
		}))
	);
}

export function removeVariable(slug: string, key: string): Promise<void> {
	return run(
		() =>
			unwrap(
				api.DELETE("/api/v1/environments/{env}/variables/{key}", {
					params: { path: { env: slug, key } },
				})
			),
		mapEnv(slug, (e) => ({
			...e,
			variables: e.variables.filter((v) => v.key !== key),
		}))
	);
}

// --- Integrations --------------------------------------------------------------------

/** Returns the integration's key (the API makes it unique). */
export async function enableIntegration(
	slug: string,
	provider: string,
	options: Partial<Omit<Integration, "provider" | "createdAt">> = {}
): Promise<string> {
	const created = await mutate(() =>
		unwrap(
			api.POST("/api/v1/environments/{env}/integrations", {
				...envPath(slug),
				body: { ...options, provider },
			})
		)
	);
	return created.id;
}

export function updateIntegration(
	slug: string,
	id: string,
	changes: Partial<Omit<Integration, "provider" | "createdAt">>
): Promise<void> {
	return run(
		() =>
			unwrap(
				api.PATCH("/api/v1/environments/{env}/integrations/{integration_id}", {
					body: changes,
					params: { path: { env: slug, integration_id: id } },
				})
			),
		mapEnv(slug, (e) => {
			const renamed = changes.id && changes.id !== id ? changes.id : null;
			return {
				...e,
				connections: renamed
					? e.connections.map((c) =>
							c.integrationId === id ? { ...c, integrationId: renamed } : c
						)
					: e.connections,
				integrations: e.integrations.map((i) =>
					i.id === id ? { ...i, ...changes } : i
				),
			};
		})
	);
}

export function deleteIntegration(slug: string, id: string): Promise<void> {
	return run(
		() =>
			unwrap(
				api.DELETE("/api/v1/environments/{env}/integrations/{integration_id}", {
					params: { path: { env: slug, integration_id: id } },
				})
			),
		mapEnv(slug, (e) => ({
			...e,
			connections: e.connections.filter((c) => c.integrationId !== id),
			integrations: e.integrations.filter((i) => i.id !== id),
		}))
	);
}

// --- Connections -----------------------------------------------------------------------

export interface NewConnection {
	credentials: Record<string, string>;
	customer: Customer;
	integrationId: string;
	sandbox: boolean;
	tags: Record<string, string>;
}

/** Creates the connection and starts its initial sync; returns its ID. */
export async function createConnection(
	slug: string,
	input: NewConnection
): Promise<string> {
	const started = await mutate(() =>
		unwrap(
			api.POST("/api/v1/environments/{env}/connections", {
				...envPath(slug),
				body: input,
			})
		)
	);
	return started.connectionId;
}

function connectionPath(slug: string, id: string) {
	return { params: { path: { connection_id: id, env: slug } } };
}

export function triggerSync(slug: string, connId: string): Promise<void> {
	return run(
		() =>
			unwrap(
				api.POST(
					"/api/v1/environments/{env}/connections/{connection_id}/sync",
					connectionPath(slug, connId)
				)
			),
		mapConnection(slug, connId, (c) =>
			c.health === "UNAUTHORIZED" ? c : { ...c, health: "SYNCING" }
		)
	);
}

export function setPaused(
	slug: string,
	connId: string,
	paused: boolean
): Promise<void> {
	return run(
		() =>
			unwrap(
				api.PATCH("/api/v1/environments/{env}/connections/{connection_id}", {
					...connectionPath(slug, connId),
					body: { paused },
				})
			),
		mapConnection(slug, connId, (c) => ({
			...c,
			health: paused ? "PAUSED" : "HEALTHY",
			paused,
		}))
	);
}

export function updateCredentials(
	slug: string,
	connId: string,
	values: Record<string, string>
): Promise<void> {
	return run(
		() =>
			unwrap(
				api.PUT(
					"/api/v1/environments/{env}/connections/{connection_id}/credentials",
					{ ...connectionPath(slug, connId), body: { values } }
				)
			),
		mapConnection(slug, connId, (c) => ({ ...c, health: "SYNCING" }))
	);
}

export function updateConnectionSettings(
	slug: string,
	connId: string,
	changes: Partial<
		Pick<
			Connection,
			"frequencyOverride" | "webhookOverride" | "tags" | "metadata"
		>
	>
): Promise<void> {
	return run(
		() =>
			unwrap(
				api.PATCH("/api/v1/environments/{env}/connections/{connection_id}", {
					...connectionPath(slug, connId),
					body: changes,
				})
			),
		mapConnection(slug, connId, (c) => ({ ...c, ...changes }))
	);
}

export function deleteConnection(slug: string, connId: string): Promise<void> {
	return run(
		() =>
			unwrap(
				api.DELETE(
					"/api/v1/environments/{env}/connections/{connection_id}",
					connectionPath(slug, connId)
				)
			),
		mapEnv(slug, (e) => ({
			...e,
			connections: e.connections.filter((c) => c.id !== connId),
		}))
	);
}

/** Simulates a customer revoking credentials, to show the unauthorized flow. */
export function simulateHealth(
	slug: string,
	connId: string,
	health: HealthCode
): Promise<void> {
	return run(
		() =>
			unwrap(
				api.POST(
					"/api/v1/environments/{env}/connections/{connection_id}/health",
					{ ...connectionPath(slug, connId), body: { health } }
				)
			),
		mapConnection(slug, connId, (c) => ({ ...c, health }))
	);
}

export interface ConnectSession {
	expiresAt: number;
	token: string;
	url: string;
}

export function createConnectSession(
	slug: string,
	customer: Customer,
	integrations: string[]
): Promise<ConnectSession> {
	return mutate(() =>
		unwrap(
			api.POST("/api/v1/environments/{env}/connect-sessions", {
				...envPath(slug),
				body: { customer, integrations },
			})
		)
	);
}

// --- Team ------------------------------------------------------------------------------

export function inviteMember(email: string, role: Role): Promise<void> {
	return run(() =>
		unwrap(api.POST("/api/v1/members", { body: { email, role } }))
	);
}

export function setMemberRole(id: string, role: Role): Promise<void> {
	return run(
		() =>
			unwrap(
				api.PATCH("/api/v1/members/{member_id}", {
					body: { role },
					params: { path: { member_id: id } },
				})
			),
		(ws) => ({
			...ws,
			members: ws.members.map((m) => (m.id === id ? { ...m, role } : m)),
		})
	);
}

export function removeMember(id: string): Promise<void> {
	return run(
		() =>
			unwrap(
				api.DELETE("/api/v1/members/{member_id}", {
					params: { path: { member_id: id } },
				})
			),
		(ws) => ({ ...ws, members: ws.members.filter((m) => m.id !== id) })
	);
}

/** Wipe and re-seed the demo workspace on the server. */
export function resetPlayground(): Promise<void> {
	return run(() => unwrap(api.POST("/api/v1/workspace/reset")));
}
