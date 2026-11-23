/**
 * Messages between the hosted connect page, its redirect popup, and the
 * embedding site (connect-js). Every message carries `source` so listeners can
 * ignore unrelated traffic; receivers also check `event.origin`.
 */
export const MESSAGE_SOURCE = "securefabric-connect";

export type ConnectMessage =
	| { source: typeof MESSAGE_SOURCE; type: "ready" }
	| {
			source: typeof MESSAGE_SOURCE;
			type: "success";
			connectionId: string;
			status: string;
	  }
	| {
			source: typeof MESSAGE_SOURCE;
			type: "error";
			code: string;
			message: string;
			connectionId?: string;
	  }
	| { source: typeof MESSAGE_SOURCE; type: "close" }
	| {
			source: typeof MESSAGE_SOURCE;
			type: "redirect_complete";
			connectionId: string;
			status: string;
	  };

/** A message before `source` is stamped on (distributes over the union). */
export type ConnectEvent = ConnectMessage extends infer M
	? M extends unknown
		? Omit<M, "source">
		: never
	: never;

export function isConnectMessage(data: unknown): data is ConnectMessage {
	return (
		typeof data === "object" &&
		data !== null &&
		(data as { source?: unknown }).source === MESSAGE_SOURCE &&
		typeof (data as { type?: unknown }).type === "string"
	);
}

/** The embedding site's origin, when connect-js passed one that parses. */
export function parentOrigin(raw: string | null): string | null {
	if (!raw) {
		return null;
	}
	try {
		const url = new URL(raw);
		return url.protocol === "https:" ||
			url.hostname === "localhost" ||
			url.hostname === "127.0.0.1"
			? url.origin
			: null;
	} catch {
		return null;
	}
}

/** Tell the embedding site (if framed) or the opener (if a popup) what happened. */
export function notifyParent(
	message: ConnectEvent,
	origin: string | null
): void {
	const full = { ...message, source: MESSAGE_SOURCE } as ConnectMessage;
	if (typeof window === "undefined" || !origin) {
		return;
	}
	if (window.parent !== window) {
		window.parent.postMessage(full, origin);
	} else if (window.opener) {
		(window.opener as Window).postMessage(full, origin);
	}
}
