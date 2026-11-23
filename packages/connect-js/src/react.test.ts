import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { MESSAGE_SOURCE } from "./index";
import { ConnectButton } from "./react";

(
	globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

describe("ConnectButton", () => {
	it("opens the flow, forwards success with the latest callback, and closes on unmount", () => {
		const container = document.createElement("div");
		document.body.append(container);
		const root = createRoot(container);
		const onSuccess = vi.fn();
		const url =
			"https://app.example.com/connect/sfcs_abcdefghijklmnopqrstuvwxyz012345";
		act(() =>
			root.render(
				createElement(ConnectButton, { onSuccess, url }, "Connect GitHub")
			)
		);
		const button = container.querySelector("button");
		expect(button?.textContent).toBe("Connect GitHub");
		act(() => button?.click());
		const frame = document.querySelector<HTMLIFrameElement>(
			"[data-securefabric-connect] iframe"
		);
		expect(frame).not.toBeNull();
		expect(container.querySelector("button")?.disabled).toBe(true);
		act(() => {
			window.dispatchEvent(
				new MessageEvent("message", {
					data: {
						connectionId: "c-1",
						source: MESSAGE_SOURCE,
						status: "active",
						type: "success",
					},
					origin: "https://app.example.com",
					source: frame?.contentWindow ?? null,
				})
			);
		});
		expect(onSuccess).toHaveBeenCalledWith({
			connectionId: "c-1",
			status: "active",
		});
		act(() => root.unmount());
		expect(document.querySelector("[data-securefabric-connect]")).toBeNull();
	});
});
