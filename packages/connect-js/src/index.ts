/**
 * @securefabric/connect-js: open SecureFabric's hosted connect flow on your
 * page, framework-free.
 *
 * ```ts
 * import { SecureFabric } from "@securefabric/connect-js";
 *
 * // `url` is what POST /v1/connect_sessions returned (or pass `token` + `baseUrl`).
 * SecureFabric.connect({
 *   url: session.url,
 *   onSuccess: ({ connectionId }) => save(connectionId),
 *   onError: ({ code, message }) => console.warn(code, message),
 *   onClose: () => refresh(),
 * }).open();
 * ```
 *
 * The flow runs in an iframe on SecureFabric's origin, so credentials never
 * touch your page. Messages are accepted only from that origin and that frame.
 * Vendor redirect steps (e.g. installing the GitHub App) open in a popup from
 * inside the frame. `mode: "popup"` runs the whole flow in a popup instead, for
 * browsers that refuse cookies in third-party frames.
 */

export const MESSAGE_SOURCE = "securefabric-connect";

export interface ConnectSuccess {
	connectionId: string;
	status: string;
}

export interface ConnectError {
	code: string;
	connectionId?: string;
	message: string;
}

export interface ConnectOptions {
	/** Where the SecureFabric dashboard is served, e.g. https://app.example.com. */
	baseUrl?: string;
	/** Mount point for the modal. Defaults to `document.body`. */
	container?: HTMLElement;
	/** `modal` (default): an iframe over your page. `popup`: a separate window. */
	mode?: "modal" | "popup";
	/** Called once, however the flow ends (success, error, or the user closing it). */
	onClose?: () => void;
	onError?: (error: ConnectError) => void;
	/** Every message from the flow, including `ready`. */
	onEvent?: (event: { type: string } & Record<string, unknown>) => void;
	onSuccess?: (result: ConnectSuccess) => void;
	/** The session token (`sfcs_…`); needs `baseUrl`. */
	token?: string;
	/** The connect link from `POST /v1/connect_sessions` (`url`). */
	url?: string;
}

export interface ConnectHandle {
	close: () => void;
	readonly isOpen: boolean;
	open: () => void;
}

const TOKEN = /^sfcs_[A-Za-z0-9_-]{16,128}$/u;
const TRAILING_SLASH = /\/+$/u;

/** The frame URL and the only origin whose messages are trusted. */
export function resolveTarget(
	options: Pick<ConnectOptions, "url" | "token" | "baseUrl">,
	embedderOrigin: string
): {
	src: string;
	origin: string;
} {
	let link: URL;
	if (options.url) {
		link = new URL(options.url);
		const token = link.pathname.split("/").at(-1) ?? "";
		if (!(link.pathname.startsWith("/connect/") && TOKEN.test(token))) {
			throw new Error(
				"SecureFabric.connect: `url` must be a connect link (…/connect/sfcs_…)."
			);
		}
	} else if (options.token && options.baseUrl) {
		if (!TOKEN.test(options.token)) {
			throw new Error(
				"SecureFabric.connect: `token` must be a connect session token (sfcs_…)."
			);
		}
		link = new URL(
			`${options.baseUrl.replace(TRAILING_SLASH, "")}/connect/${options.token}`
		);
	} else {
		throw new Error(
			"SecureFabric.connect: pass `url`, or `token` with `baseUrl`."
		);
	}
	if (
		link.protocol !== "https:" &&
		!["localhost", "127.0.0.1"].includes(link.hostname)
	) {
		throw new Error("SecureFabric.connect: the connect link must use https.");
	}
	link.search = "";
	link.hash = "";
	link.searchParams.set("origin", embedderOrigin);
	return { origin: link.origin, src: link.toString() };
}

interface Message {
	source: string;
	type: string;
	[key: string]: unknown;
}

function isMessage(data: unknown): data is Message {
	return (
		typeof data === "object" &&
		data !== null &&
		(data as Message).source === MESSAGE_SOURCE &&
		typeof (data as Message).type === "string"
	);
}

const Z_TOP = "2147483647";

function el<K extends keyof HTMLElementTagNameMap>(
	tag: K,
	style: Partial<CSSStyleDeclaration>
): HTMLElementTagNameMap[K] {
	const node = document.createElement(tag);
	Object.assign(node.style, style);
	return node;
}

function buildModal(
	src: string,
	onDismiss: () => void
): { root: HTMLElement; frame: HTMLIFrameElement } {
	const root = el("div", {
		alignItems: "center",
		background: "rgba(15, 23, 42, 0.55)",
		display: "flex",
		inset: "0",
		justifyContent: "center",
		position: "fixed",
		zIndex: Z_TOP,
	});
	root.setAttribute("data-securefabric-connect", "");
	root.setAttribute("role", "dialog");
	root.setAttribute("aria-modal", "true");
	root.setAttribute("aria-label", "Connect an account");
	const frame = el("iframe", {
		background: "transparent",
		border: "0",
		borderRadius: "12px",
		boxShadow: "0 24px 48px rgba(0,0,0,0.25)",
		height: "min(720px, calc(100% - 32px))",
		maxWidth: "calc(100% - 32px)",
		width: "480px",
	});
	frame.src = src;
	frame.title = "Connect an account";
	frame.setAttribute("allow", "clipboard-write");
	frame.setAttribute(
		"sandbox",
		"allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
	);
	const close = el("button", {
		background: "rgba(255,255,255,0.9)",
		border: "0",
		borderRadius: "999px",
		cursor: "pointer",
		fontSize: "18px",
		height: "32px",
		position: "absolute",
		right: "16px",
		top: "16px",
		width: "32px",
	});
	close.type = "button";
	close.textContent = "×";
	close.setAttribute("aria-label", "Close");
	close.addEventListener("click", onDismiss);
	root.addEventListener("click", (e) => {
		if (e.target === root) {
			onDismiss();
		}
	});
	root.append(frame, close);
	return { frame, root };
}

export function connect(options: ConnectOptions): ConnectHandle {
	const mode = options.mode ?? "modal";
	let target: { src: string; origin: string } | null = null;
	let root: HTMLElement | null = null;
	let source: Window | null = null;
	let popupTimer: ReturnType<typeof setInterval> | null = null;
	let open = false;
	let previousOverflow = "";

	const onKey = (e: KeyboardEvent) => {
		if (e.key === "Escape") {
			close();
		}
	};

	const onMessage = (event: MessageEvent) => {
		if (
			!target ||
			event.origin !== target.origin ||
			event.source !== source ||
			!isMessage(event.data)
		) {
			return;
		}
		const { source: _source, ...data } = event.data;
		options.onEvent?.(data as { type: string } & Record<string, unknown>);
		switch (data.type) {
			case "success":
				options.onSuccess?.({
					connectionId: String(data.connectionId),
					status: String(data.status ?? "active"),
				});
				break;
			case "error":
				options.onError?.({
					code: String(data.code ?? "unknown"),
					connectionId:
						typeof data.connectionId === "string"
							? data.connectionId
							: undefined,
					message: String(data.message ?? ""),
				});
				break;
			case "close":
				close();
				break;
			default:
				break;
		}
	};

	function close(): void {
		if (!open) {
			return;
		}
		open = false;
		window.removeEventListener("message", onMessage);
		document.removeEventListener("keydown", onKey);
		if (popupTimer) {
			clearInterval(popupTimer);
			popupTimer = null;
		}
		if (root) {
			root.remove();
			document.body.style.overflow = previousOverflow;
			root = null;
		} else if (source && !source.closed) {
			source.close();
		}
		source = null;
		options.onClose?.();
	}

	function openFlow(): void {
		if (open) {
			return;
		}
		target = resolveTarget(options, window.location.origin);
		open = true;
		window.addEventListener("message", onMessage);
		if (mode === "popup") {
			source = window.open(
				target.src,
				"securefabric-connect",
				"popup,width=520,height=760"
			);
			if (!source) {
				open = false;
				window.removeEventListener("message", onMessage);
				options.onError?.({
					code: "popup_blocked",
					message: "The browser blocked the connect window.",
				});
				options.onClose?.();
				return;
			}
			popupTimer = setInterval(() => {
				if (source?.closed) {
					close();
				}
			}, 500);
			return;
		}
		const modal = buildModal(target.src, close);
		({ root } = modal);
		previousOverflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		(options.container ?? document.body).append(root);
		source = modal.frame.contentWindow;
		document.addEventListener("keydown", onKey);
	}

	return {
		close,
		get isOpen() {
			return open;
		},
		open: openFlow,
	};
}

export const SecureFabric = { connect };
