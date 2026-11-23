import { createRng } from "./random";
import type { Environment, Operation, Webhook, WebhookEvent } from "./types";
import { WEBHOOK_EVENTS } from "./types";

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export type EventGroup = "Connections" | "Syncs" | "Actions";

/** What each event means, for the event picker and the delivery list. */
export const WEBHOOK_EVENT_INFO: Record<
	WebhookEvent,
	{ group: EventGroup; description: string }
> = {
	"action.completed": {
		description: "A write action such as isolating a device finished.",
		group: "Actions",
	},
	"action.failed": {
		description: "A write action was rejected by the vendor or timed out.",
		group: "Actions",
	},
	"connection.create.failed": {
		description:
			"A customer started SecureFabric Connect but the credentials didn't work.",
		group: "Connections",
	},
	"connection.create.succeeded": {
		description: "A customer finished SecureFabric Connect.",
		group: "Connections",
	},
	"connection.deleted": {
		description: "A connection was removed and its data deleted.",
		group: "Connections",
	},
	"connection.sync.failed": {
		description: "A sync stopped early. Data from the last good sync is kept.",
		group: "Syncs",
	},
	"connection.sync.succeeded": {
		description: "New or changed records are ready to read.",
		group: "Syncs",
	},
	"connection.sync.unauthorized": {
		description:
			"Stored credentials stopped working. Ask the customer to reconnect.",
		group: "Syncs",
	},
};

export const EVENT_GROUPS: EventGroup[] = ["Connections", "Syncs", "Actions"];

export function eventsIn(group: EventGroup): WebhookEvent[] {
	return WEBHOOK_EVENTS.filter((e) => WEBHOOK_EVENT_INFO[e].group === group);
}

/** Svix-style backoff: how long after each failed attempt the next runs. */
const RETRY_DELAYS = [
	5000,
	5 * MINUTE,
	30 * MINUTE,
	2 * HOUR,
	5 * HOUR,
	10 * HOUR,
];

export interface DeliveryAttempt {
	at: number;
	durationMs: number;
	/** Set when no HTTP response came back at all. */
	error?: string;
	response: string;
	statusCode: number | null;
}

export type DeliveryStatus = "succeeded" | "retrying" | "failed";

export interface Delivery {
	attempts: DeliveryAttempt[];
	connectionId: string | null;
	customer: string | null;
	event: WebhookEvent | "ping";
	/** The `webhook-id` header; stays the same across retries. */
	id: string;
	nextRetryAt: number | null;
	payload: Record<string, unknown>;
	startedAt: number;
	status: DeliveryStatus;
}

function eventOf(op: Operation): WebhookEvent | "ping" | null {
	const name = op.action.replace("webhook.", "");
	if (name === "ping") {
		return "ping";
	}
	return WEBHOOK_EVENTS.find((e) => e === name) ?? null;
}

function belongsTo(
	op: Operation,
	hook: Webhook,
	event: WebhookEvent | "ping"
): boolean {
	// Test sends and resends name their endpoint; seeded history doesn't, so
	// it goes to every endpoint subscribed to the event at the time.
	if (op.path) {
		return op.path === hook.url;
	}
	return (
		event !== "ping" &&
		hook.events.includes(event) &&
		op.startedAt >= hook.createdAt
	);
}

const OK_BODY = '{"received":true}';

/**
 * Attempts for one delivery. The history only records that the event went
 * out, so failures are rolled from the delivery's id: stable across reloads,
 * rare, and mostly recovered by a retry, the way a real endpoint behaves.
 */
function attemptsFor(
	op: Operation,
	now: number
): Pick<Delivery, "attempts" | "nextRetryAt" | "status"> {
	const rng = createRng(`${op.id}:delivery`);
	const ok = (at: number): DeliveryAttempt => ({
		at,
		durationMs: op.durationMs,
		response: OK_BODY,
		statusCode: 200,
	});
	const fail = (at: number): DeliveryAttempt =>
		rng.bool(0.5)
			? {
					at,
					durationMs: 15_000,
					error: "Timed out after 15s",
					response: "",
					statusCode: null,
				}
			: {
					at,
					durationMs: rng.int(40, 400),
					response: rng.pick(["Bad Gateway", "Service Unavailable"]),
					statusCode: rng.pick([502, 503]),
				};

	const roll = rng.next();
	const isTest = Boolean(op.path);
	if (isTest || roll > 0.07) {
		return {
			attempts: [ok(op.startedAt)],
			nextRetryAt: null,
			status: "succeeded",
		};
	}
	const first = fail(op.startedAt);
	const recent = now - op.startedAt < 20 * MINUTE;
	if (recent && roll < 0.03) {
		return {
			attempts: [first],
			nextRetryAt: op.startedAt + (RETRY_DELAYS[1] ?? MINUTE),
			status: "retrying",
		};
	}
	const second = (RETRY_DELAYS[0] ?? 0) + op.startedAt;
	if (roll < 0.015) {
		// Ran out of retries: every attempt in the schedule failed.
		let at = op.startedAt;
		const attempts = [first];
		for (const delay of RETRY_DELAYS) {
			at += delay;
			if (at > now) {
				break;
			}
			attempts.push(fail(at));
		}
		return { attempts, nextRetryAt: null, status: "failed" };
	}
	return {
		attempts: [first, ok(second)],
		nextRetryAt: null,
		status: "succeeded",
	};
}

const PAYLOAD_ERRORS: Partial<Record<WebhookEvent, string>> = {
	"connection.create.failed": "CONNECTION_CREATE_FAILED",
	"connection.sync.unauthorized": "UNAUTHORIZED",
};

/** The event body: Leen-style envelope with the connection at the root and
 * event details under `data`. */
function payloadFor(
	op: Operation,
	event: WebhookEvent | "ping",
	environmentId: string
): Record<string, unknown> {
	const type = event === "ping" ? "webhook.ping" : event;
	const vendor = op.provider
		? op.provider.toLowerCase().replaceAll("-", "_")
		: null;
	const data: Record<string, unknown> =
		event === "ping"
			? { description: "Test event from the SecureFabric dashboard" }
			: {
					customer: op.customer,
					error: PAYLOAD_ERRORS[event] ?? null,
					integration_id: op.integrationId,
					vendor,
					...(op.records === undefined ? {} : { records_synced: op.records }),
				};
	return {
		connection_id: op.connectionId,
		created_at: new Date(op.startedAt).toISOString(),
		data,
		environment_id: environmentId,
		id: `evt_${op.id.slice(3)}`,
		type,
	};
}

/** One endpoint's deliveries, newest first. */
export function deliveriesFor(
	env: Environment,
	hook: Webhook,
	now = Date.now()
): Delivery[] {
	const out: Delivery[] = [];
	for (const op of env.operations) {
		if (op.type !== "webhook") {
			continue;
		}
		const event = eventOf(op);
		if (!(event && belongsTo(op, hook, event))) {
			continue;
		}
		out.push({
			...attemptsFor(op, now),
			connectionId: op.connectionId,
			customer: op.customer,
			event,
			id: `msg_${op.id.slice(3)}`,
			payload: payloadFor(op, event, env.id),
			startedAt: op.startedAt,
		});
	}
	return out.sort((a, b) => b.startedAt - a.startedAt);
}

export interface EndpointStats {
	avgMs: number | null;
	failed: number;
	last: Delivery | null;
	successRate: number | null;
	total: number;
}

/** The last 7 days, the window an endpoint's health is judged over. */
export function endpointStats(
	deliveries: Delivery[],
	now = Date.now()
): EndpointStats {
	const week = deliveries.filter((d) => d.startedAt >= now - 7 * DAY);
	const done = week.filter((d) => d.status !== "retrying");
	const ok = done.filter((d) => d.status === "succeeded");
	const lastAttempts = ok
		.map((d) => d.attempts.at(-1)?.durationMs)
		.filter((ms): ms is number => ms !== undefined);
	return {
		avgMs: lastAttempts.length
			? Math.round(
					lastAttempts.reduce((a, b) => a + b, 0) / lastAttempts.length
				)
			: null,
		failed: week.filter((d) => d.status !== "succeeded").length,
		last: deliveries[0] ?? null,
		successRate: done.length ? ok.length / done.length : null,
		total: week.length,
	};
}

/** The headers every delivery carries; the signature matches the scheme
 * the verify sample in Settings checks (t=timestamp, v1=HMAC-SHA256). */
export function deliveryHeaders(delivery: Delivery): Record<string, string> {
	const ts = Math.floor(delivery.startedAt / 1000);
	const sig = createRng(`${delivery.id}:sig`).hex(64);
	return {
		"Content-Type": "application/json",
		"User-Agent": "SecureFabric-Webhooks/1.0",
		"X-SecureFabric-Delivery": delivery.id,
		"X-SecureFabric-Event":
			delivery.event === "ping" ? "webhook.ping" : delivery.event,
		"X-SecureFabric-Signature": `t=${ts},v1=${sig}`,
	};
}
