import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { connect, MESSAGE_SOURCE, resolveTarget } from "./index";

const TOKEN = "sfcs_abcdefghijklmnopqrstuvwxyz012345";
const URL_ = `https://app.example.com/connect/${TOKEN}`;
const ORIGIN = "https://app.example.com";
const CONNECT_LINK = /connect link/u;
const HTTPS = /https/u;
const BASE_URL = /baseUrl/u;
const TOKEN_RE = /token/u;

function frame(): HTMLIFrameElement {
	const f = document.querySelector<HTMLIFrameElement>(
		"[data-securefabric-connect] iframe"
	);
	if (!f) {
		throw new Error("no frame");
	}
	return f;
}

function post(
	data: unknown,
	origin = ORIGIN,
	source: MessageEventSource | null = frame().contentWindow
) {
	window.dispatchEvent(new MessageEvent("message", { data, origin, source }));
}

describe("resolveTarget", () => {
	it("builds the frame URL from a connect link and adds the embedder origin", () => {
		const t = resolveTarget({ url: `${URL_}?x=1#y` }, "https://customer.test");
		expect(t.origin).toBe(ORIGIN);
		expect(t.src).toBe(
			`${URL_}?origin=${encodeURIComponent("https://customer.test")}`
		);
	});

	it("accepts a token with a base URL", () => {
		expect(
			resolveTarget({ baseUrl: `${ORIGIN}/`, token: TOKEN }, "https://c.test")
				.src
		).toContain(`/connect/${TOKEN}?`);
	});

	it("rejects links that are not connect links, non-https links and missing input", () => {
		expect(() =>
			resolveTarget({ url: `${ORIGIN}/settings` }, "https://c.test")
		).toThrow(CONNECT_LINK);
		expect(() =>
			resolveTarget(
				{ url: `http://evil.test/connect/${TOKEN}` },
				"https://c.test"
			)
		).toThrow(HTTPS);
		expect(() => resolveTarget({ token: TOKEN }, "https://c.test")).toThrow(
			BASE_URL
		);
		expect(() =>
			resolveTarget({ baseUrl: ORIGIN, token: "nope" }, "https://c.test")
		).toThrow(TOKEN_RE);
	});

	it("allows http on localhost for development", () => {
		expect(
			resolveTarget(
				{ url: `http://localhost:3000/connect/${TOKEN}` },
				"http://localhost:5173"
			).origin
		).toBe("http://localhost:3000");
	});
});

describe("connect (modal)", () => {
	beforeEach(() => {
		document.body.innerHTML = "";
		document.body.style.overflow = "";
	});
	afterEach(() => vi.restoreAllMocks());

	it("mounts a sandboxed frame and locks page scroll", () => {
		const h = connect({ url: URL_ });
		h.open();
		expect(h.isOpen).toBe(true);
		expect(frame().getAttribute("sandbox")).toContain("allow-scripts");
		expect(frame().src).toContain(`/connect/${TOKEN}?origin=`);
		expect(document.body.style.overflow).toBe("hidden");
		h.close();
	});

	it("delivers success from the frame's origin", () => {
		const onSuccess = vi.fn();
		const onEvent = vi.fn();
		const h = connect({ onEvent, onSuccess, url: URL_ });
		h.open();
		post({ source: MESSAGE_SOURCE, type: "ready" });
		post({
			connectionId: "c-1",
			source: MESSAGE_SOURCE,
			status: "active",
			type: "success",
		});
		expect(onEvent).toHaveBeenCalledWith({ type: "ready" });
		expect(onSuccess).toHaveBeenCalledWith({
			connectionId: "c-1",
			status: "active",
		});
		h.close();
	});

	it("ignores messages from other origins, other windows, and other shapes", () => {
		const onSuccess = vi.fn();
		const onError = vi.fn();
		const h = connect({ onError, onSuccess, url: URL_ });
		h.open();
		const msg = {
			connectionId: "c-1",
			source: MESSAGE_SOURCE,
			status: "active",
			type: "success",
		};
		post(msg, "https://evil.test");
		post(msg, ORIGIN, window);
		post({ ...msg, source: "someone-else" });
		post("success");
		expect(onSuccess).not.toHaveBeenCalled();
		expect(onError).not.toHaveBeenCalled();
		h.close();
	});

	it("reports errors", () => {
		const onError = vi.fn();
		const h = connect({ onError, url: URL_ });
		h.open();
		post({
			code: "UNAUTHORIZED",
			message: "bad token",
			source: MESSAGE_SOURCE,
			type: "error",
		});
		expect(onError).toHaveBeenCalledWith({
			code: "UNAUTHORIZED",
			connectionId: undefined,
			message: "bad token",
		});
		h.close();
	});

	it("closes on Escape, on a close message, and calls onClose exactly once", () => {
		const onClose = vi.fn();
		const h = connect({ onClose, url: URL_ });
		h.open();
		document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
		expect(h.isOpen).toBe(false);
		expect(document.querySelector("[data-securefabric-connect]")).toBeNull();
		expect(document.body.style.overflow).toBe("");
		h.close();
		expect(onClose).toHaveBeenCalledTimes(1);

		const h2 = connect({ onClose, url: URL_ });
		h2.open();
		post({ source: MESSAGE_SOURCE, type: "close" });
		expect(h2.isOpen).toBe(false);
		expect(onClose).toHaveBeenCalledTimes(2);
	});

	it("stops listening after close", () => {
		const onSuccess = vi.fn();
		const h = connect({ onSuccess, url: URL_ });
		h.open();
		const source = frame().contentWindow;
		h.close();
		post(
			{
				connectionId: "c",
				source: MESSAGE_SOURCE,
				status: "active",
				type: "success",
			},
			ORIGIN,
			source
		);
		expect(onSuccess).not.toHaveBeenCalled();
	});
});

describe("connect (popup)", () => {
	afterEach(() => vi.restoreAllMocks());

	it("opens a window and trusts only it", () => {
		const popup = { close: vi.fn(), closed: false } as unknown as Window;
		const openSpy = vi.spyOn(window, "open").mockReturnValue(popup);
		const onSuccess = vi.fn();
		const h = connect({ mode: "popup", onSuccess, url: URL_ });
		h.open();
		expect(openSpy).toHaveBeenCalledWith(
			expect.stringContaining(`/connect/${TOKEN}?origin=`),
			"securefabric-connect",
			expect.any(String)
		);
		window.dispatchEvent(
			new MessageEvent("message", {
				data: {
					connectionId: "c-9",
					source: MESSAGE_SOURCE,
					status: "active",
					type: "success",
				},
				origin: ORIGIN,
				source: popup as unknown as MessageEventSource,
			})
		);
		expect(onSuccess).toHaveBeenCalledWith({
			connectionId: "c-9",
			status: "active",
		});
		h.close();
		expect(popup.close).toHaveBeenCalled();
	});

	it("reports a blocked popup", () => {
		vi.spyOn(window, "open").mockReturnValue(null);
		const onError = vi.fn();
		const onClose = vi.fn();
		const h = connect({ mode: "popup", onClose, onError, url: URL_ });
		h.open();
		expect(onError).toHaveBeenCalledWith(
			expect.objectContaining({ code: "popup_blocked" })
		);
		expect(onClose).toHaveBeenCalledTimes(1);
		expect(h.isOpen).toBe(false);
	});
});
