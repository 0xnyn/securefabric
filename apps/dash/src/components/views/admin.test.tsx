// @vitest-environment jsdom

import { createClient } from "@securefabric/client";
import { TooltipProvider } from "@securefabric/ui/components/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EnvContext } from "@/components/shell/env-context";
import type { Environment, Me } from "@/lib/types";
import { AdminView, type Alert } from "./admin";

(
	globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

const nav = vi.hoisted(() => ({ search: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
	usePathname: () => "/dev/admin",
	useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
	useSearchParams: () => nav.search,
}));

vi.mock("next/link", () => ({
	default: ({
		href,
		children,
		...rest
	}: {
		href: string;
		children: React.ReactNode;
	}) => (
		<a href={href} {...rest}>
			{children}
		</a>
	),
}));

const ENV: Environment = {
	created_at: null,
	id: "11111111-1111-1111-1111-111111111111",
	is_production: false,
	name: "Development",
	settings: {},
	slug: "dev",
};

const CUSTOMER_ENV = "33333333-3333-3333-3333-333333333333";
const CONNECTION = "44444444-4444-4444-4444-444444444444";

function me(isOperator: boolean): Me {
	return {
		environments: [ENV],
		is_operator: isOperator,
		kind: isOperator ? "user" : "api_key",
		needs_onboarding: false,
	} as unknown as Me;
}

function alert(id: string, overrides: Partial<Alert> = {}): Alert {
	return {
		detail: {},
		id,
		name: "stuck_runs",
		raised_at: "2026-11-23T08:00:00.000Z",
		resolved_at: null,
		runbook: "docs/runbooks/stuck-runs.md",
		severity: "page",
		subject: "environment dev",
		...overrides,
	};
}

interface Sent {
	body: unknown;
	headers: Headers;
	method: string;
	url: URL;
}

const json = (body: unknown, status = 200) =>
	new Response(JSON.stringify(body), {
		headers: {
			"content-type":
				status >= 400 ? "application/problem+json" : "application/json",
		},
		status,
	});

const OPERATOR_REQUIRED = {
	code: "operator_required",
	detail: "Operators only.",
	errors: [],
	request_id: "req_1",
	status: 403,
	title: "Forbidden",
	type: "about:blank",
};

/** A stub API: records every request and answers with `route`. */
function stubApi(route: (sent: Sent) => Response) {
	const requests: Sent[] = [];
	const fetchStub = async (req: Request) => {
		const text = req.method === "GET" ? "" : await req.clone().text();
		const sent: Sent = {
			body: text ? JSON.parse(text) : null,
			headers: req.headers,
			method: req.method,
			url: new URL(req.url),
		};
		requests.push(sent);
		return route(sent);
	};
	return {
		admin: () => requests.filter((r) => r.url.pathname.includes("/v1/admin")),
		client: createClient("http://test/api/sf", { fetch: fetchStub }),
		requests,
	};
}

/** Sets an input's value the way React notices (it tracks the native setter). */
function type(el: HTMLInputElement | HTMLTextAreaElement, value: string) {
	const proto =
		el instanceof HTMLTextAreaElement
			? HTMLTextAreaElement.prototype
			: HTMLInputElement.prototype;
	Object.getOwnPropertyDescriptor(proto, "value")?.set?.call(el, value);
	el.dispatchEvent(new Event("input", { bubbles: true }));
}

const settle = () => act(() => new Promise((r) => setTimeout(r, 20)));

function button(scope: ParentNode, text: string): HTMLButtonElement {
	const found = [...scope.querySelectorAll("button")].find(
		(b) => b.textContent?.trim() === text
	);
	if (!found) {
		throw new Error(`No button "${text}"`);
	}
	return found;
}

describe("<AdminView>", () => {
	let container: HTMLDivElement;
	let root: Root;
	beforeEach(() => {
		nav.search = new URLSearchParams();
		container = document.createElement("div");
		document.body.append(container);
		root = createRoot(container);
	});
	afterEach(() => {
		act(() => root.unmount());
		container.remove();
		document.body.innerHTML = "";
	});

	async function render(
		api: ReturnType<typeof stubApi>,
		{ operator = true, devMode = false } = {}
	) {
		const queryClient = new QueryClient({
			defaultOptions: { queries: { retry: false } },
		});
		await act(() => {
			root.render(
				<QueryClientProvider client={queryClient}>
					<TooltipProvider>
						<EnvContext
							value={{
								client: api.client,
								devMode,
								env: ENV,
								environments: [ENV],
								me: me(operator),
							}}
						>
							<AdminView />
						</EnvContext>
					</TooltipProvider>
				</QueryClientProvider>
			);
		});
		await settle();
	}

	describe("operator gate", () => {
		it("shows the gate to a non-operator without calling the admin API", async () => {
			const api = stubApi(() => json([]));
			await render(api, { devMode: true, operator: false });
			expect(container.textContent).toContain("Operator access required");
			expect(container.textContent).toContain("development API key");
			expect(container.querySelector("[role='tablist']")).toBeNull();
			expect(api.admin()).toHaveLength(0);
		});

		it("shows the gate, not an error, when the API answers operator_required", async () => {
			const api = stubApi(() => json(OPERATOR_REQUIRED, 403));
			await render(api);
			expect(api.admin()).toHaveLength(1);
			expect(container.textContent).toContain("Operator access required");
			expect(container.textContent).not.toContain("Couldn't load this");
		});
	});

	describe("alerts", () => {
		const A1 = "aaaaaaaa-0000-0000-0000-000000000001";
		const A2 = "bbbbbbbb-0000-0000-0000-000000000002";

		function alertsApi() {
			return stubApi(({ method, url, body }) => {
				if (method === "POST" && url.pathname.endsWith(`/${A1}/resolve`)) {
					return json(
						alert(A1, {
							detail: {
								resolution: {
									by: "user:u1",
									note: (body as { note: string }).note,
								},
							},
							resolved_at: "2026-11-23T09:00:00.000Z",
						})
					);
				}
				if (url.pathname.endsWith("/v1/admin/alerts")) {
					const open = [
						alert(A1),
						alert(A2, {
							name: "queue_backlog",
							runbook: "docs/runbooks/queue-backlog.md",
							severity: "ticket",
							subject: "queue sync",
						}),
					];
					return json(
						url.searchParams.get("include_resolved") === "true"
							? [
									...open,
									alert("cccccccc-0000-0000-0000-000000000003", {
										detail: { resolution: { by: "user:u1", note: "fixed" } },
										name: "old_one",
										resolved_at: "2026-11-22T09:00:00.000Z",
									}),
								]
							: open
					);
				}
				return json([]);
			});
		}

		const rows = () => [...container.querySelectorAll("tbody tr")];

		it("lists open alerts with severity, subject and runbook", async () => {
			const api = alertsApi();
			await render(api);
			const [list] = api.admin();
			expect(list?.url.pathname).toBe("/api/sf/v1/admin/alerts");
			expect(list?.url.searchParams.get("include_resolved")).toBe("false");
			expect(rows()).toHaveLength(2);
			expect(rows()[0]?.textContent).toContain("Page");
			expect(rows()[0]?.textContent).toContain("stuck_runs");
			expect(rows()[0]?.textContent).toContain("environment dev");
			expect(rows()[0]?.textContent).toContain("docs/runbooks/stuck-runs.md");
			expect(rows()[1]?.textContent).toContain("Ticket");
			expect(button(rows()[0] as HTMLElement, "Resolve")).toBeTruthy();
		});

		it("includes resolved alerts when toggled", async () => {
			const api = alertsApi();
			await render(api);
			await act(() => {
				container.querySelector<HTMLElement>("[role='switch']")?.click();
			});
			await settle();
			expect(
				api
					.admin()
					.some((r) => r.url.searchParams.get("include_resolved") === "true")
			).toBe(true);
			expect(rows()).toHaveLength(3);
			expect(rows()[2]?.textContent).toContain("Resolved");
			expect(rows()[2]?.textContent).toContain("fixed");
		});

		it("resolves an alert with the note", async () => {
			const api = alertsApi();
			await render(api);
			await act(() => {
				button(rows()[0] as HTMLElement, "Resolve").click();
			});
			await settle();
			const dialog = document.querySelector<HTMLElement>("[role='dialog']");
			expect(dialog).not.toBeNull();
			const submit = button(dialog as HTMLElement, "Resolve alert");
			expect(submit.disabled).toBe(true);
			const note = dialog?.querySelector("textarea");
			await act(() => {
				type(
					note as HTMLTextAreaElement,
					"  Re-probed; customer rotated the key.  "
				);
			});
			expect(submit.disabled).toBe(false);
			const before = api.admin().length;
			await act(() => {
				submit.click();
			});
			await settle();
			const post = api.admin().find((r) => r.method === "POST");
			expect(post?.url.pathname).toBe(`/api/sf/v1/admin/alerts/${A1}/resolve`);
			expect(post?.body).toEqual({
				note: "Re-probed; customer rotated the key.",
			});
			// The list is fetched again after resolving.
			expect(
				api
					.admin()
					.slice(before)
					.filter((r) => r.method === "GET").length
			).toBeGreaterThan(0);
		});
	});

	describe("repairs", () => {
		function repairApi() {
			return stubApi(({ method }) =>
				method === "POST"
					? json({ job_id: "55555555-5555-5555-5555-555555555555" })
					: json([])
			);
		}

		async function openRepairs(api: ReturnType<typeof stubApi>) {
			nav.search = new URLSearchParams({
				connection: CONNECTION,
				environment: CUSTOMER_ENV,
				tab: "repairs",
			});
			await render(api);
		}

		const choose = async (action: string) => {
			await act(() => {
				container
					.querySelector<HTMLInputElement>(
						`input[type='radio'][value='${action}']`
					)
					?.click();
			});
		};

		const reason = async (text: string) => {
			await act(() => {
				type(container.querySelector("textarea") as HTMLTextAreaElement, text);
			});
		};

		it("prefills the target from the URL", async () => {
			await openRepairs(repairApi());
			const inputs = [
				...container.querySelectorAll<HTMLInputElement>("input.font-mono"),
			].map((i) => i.value);
			expect(inputs).toEqual([CUSTOMER_ENV, CONNECTION]);
		});

		it("needs a support reason and sends it as X-Support-Reason", async () => {
			const api = repairApi();
			await openRepairs(api);
			const run = button(container, "Run trigger");
			expect(run.disabled).toBe(true);
			expect(container.textContent).toContain("Needs a support reason");
			await reason("Ticket 4821: stuck sync");
			expect(run.disabled).toBe(false);
			await act(() => {
				run.click();
			});
			await settle();
			const post = api.requests.find((r) => r.method === "POST");
			expect(post?.url.pathname).toBe(
				`/api/sf/v1/admin/environments/${CUSTOMER_ENV}/connections/${CONNECTION}/trigger`
			);
			expect(post?.headers.get("X-Support-Reason")).toBe(
				"Ticket 4821: stuck sync"
			);
			expect(post?.body).toEqual({ params: {} });
			expect(container.textContent).toContain(
				"55555555-5555-5555-5555-555555555555"
			);
		});

		it("asks before a reset and sends wipe", async () => {
			const api = repairApi();
			await openRepairs(api);
			await choose("reset");
			await reason("Ticket 4822: corrupted cursor");
			await act(() => {
				container.querySelector<HTMLElement>("[role='switch']")?.click();
			});
			await act(() => {
				button(container, "Run reset").click();
			});
			await settle();
			expect(api.requests.some((r) => r.method === "POST")).toBe(false);
			const dialog = document.querySelector<HTMLElement>("[role='dialog']");
			expect(dialog?.textContent).toContain("after deleting its rows");
			await act(() => {
				button(dialog as HTMLElement, "Run reset").click();
			});
			await settle();
			const posts = api.requests.filter((r) => r.method === "POST");
			expect(posts).toHaveLength(1);
			expect(posts[0]?.url.pathname).toBe(
				`/api/sf/v1/admin/environments/${CUSTOMER_ENV}/connections/${CONNECTION}/reset`
			);
			expect(posts[0]?.headers.get("X-Support-Reason")).toBe(
				"Ticket 4822: corrupted cursor"
			);
			expect(posts[0]?.body).toEqual({ params: { wipe: true } });
		});

		it("sends nothing when a reset is cancelled", async () => {
			const api = repairApi();
			await openRepairs(api);
			await choose("reset");
			await reason("Ticket 4823: checking");
			await act(() => {
				button(container, "Run reset").click();
			});
			await settle();
			const dialog = document.querySelector<HTMLElement>("[role='dialog']");
			await act(() => {
				button(dialog as HTMLElement, "Cancel").click();
			});
			await settle();
			expect(api.requests.some((r) => r.method === "POST")).toBe(false);
		});

		it("shows stream_required under the Stream field", async () => {
			const api = stubApi(({ method }) =>
				method === "POST"
					? json(
							{
								code: "stream_required",
								detail:
									"renormalize needs params.stream, one of the connector's streams.",
								errors: [
									{
										field: "params.stream",
										message: "one of ['findings', 'repositories']",
									},
								],
								request_id: "req_2",
								status: 422,
								title: "Validation failed",
								type: "about:blank",
							},
							422
						)
					: json([])
			);
			await openRepairs(api);
			await choose("renormalize");
			await reason("Ticket 4824: re-normalize");
			const stream = container.querySelector<HTMLInputElement>(
				"input[placeholder='findings']"
			) as HTMLInputElement;
			await act(() => {
				type(stream, "bogus");
			});
			await act(() => {
				button(container, "Run renormalize").click();
			});
			await settle();
			const [post] = api.requests.filter((r) => r.method === "POST");
			expect(post?.body).toEqual({ params: { stream: "bogus" } });
			expect(stream.getAttribute("aria-invalid")).toBe("true");
			const error = stream
				.closest("div")
				?.querySelector<HTMLElement>("[role='alert']");
			expect(error?.textContent).toBe("one of ['findings', 'repositories']");
			// Editing the stream clears the error.
			await act(() => {
				type(stream, "findings");
			});
			expect(stream.hasAttribute("aria-invalid")).toBe(false);
		});

		describe("queued repairs", () => {
			const TASK = "66666666-6666-6666-6666-666666666666";

			beforeEach(() => {
				vi.useFakeTimers({ shouldAdvanceTime: true });
			});
			afterEach(() => {
				vi.useRealTimers();
			});

			/** POST answers `{ task_id }`; each status poll takes the next state. */
			function queuedApi(states: Record<string, unknown>[]) {
				let polls = 0;
				const api = stubApi(({ method, url }) => {
					if (method === "POST") {
						return json({ status: "queued", task_id: TASK });
					}
					if (url.pathname.endsWith(`/v1/admin/repairs/${TASK}`)) {
						const state = states[Math.min(polls, states.length - 1)];
						polls += 1;
						return json({
							failure: null,
							result: null,
							task_id: TASK,
							...state,
						});
					}
					return json([]);
				});
				return { ...api, polls: () => polls };
			}

			const tick = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));

			it("polls a queued repair until it completes and shows the result", async () => {
				const api = queuedApi([
					{ state: "pending" },
					{ state: "running" },
					{ result: { purged: 3 }, state: "completed" },
				]);
				await openRepairs(api);
				await choose("purge_now");
				await reason("Ticket 4825: purge requested");
				await act(() => {
					button(container, "Run purge_now").click();
				});
				await settle();
				const dialog = document.querySelector<HTMLElement>("[role='dialog']");
				await act(() => {
					button(dialog as HTMLElement, "Run purge_now").click();
				});
				await settle();
				const task = () =>
					container.querySelector<HTMLElement>(`[data-repair-task='${TASK}']`);
				expect(task()?.textContent).toContain("Pending");
				expect(api.polls()).toBe(1);
				await tick(2000);
				expect(task()?.textContent).toContain("Running");
				await tick(2000);
				expect(task()?.textContent).toContain("Completed");
				expect(task()?.textContent).toContain('"purged": 3');
				await tick(6000);
				expect(api.polls()).toBe(3);
			});

			it("shows the failure's name and message and stops polling", async () => {
				const api = queuedApi([
					{ state: "running" },
					{
						failure: {
							message: "vendor answered 401",
							name: "VendorAuthError",
						},
						state: "failed",
					},
				]);
				await openRepairs(api);
				await choose("reprobe");
				await reason("Ticket 4826: credentials");
				await act(() => {
					button(container, "Run reprobe").click();
				});
				await settle();
				await tick(2000);
				const task = container.querySelector<HTMLElement>(
					`[data-repair-task='${TASK}']`
				);
				expect(task?.textContent).toContain("Failed");
				const failure = task?.querySelector<HTMLElement>("[role='alert']");
				expect(failure?.textContent).toContain("VendorAuthError");
				expect(failure?.textContent).toContain("vendor answered 401");
				await tick(6000);
				expect(api.polls()).toBe(2);
			});

			it("does not poll repairs that answer synchronously", async () => {
				const api = queuedApi([{ state: "completed" }]);
				await openRepairs(api);
				await choose("pause");
				await reason("Ticket 4827: pause");
				await act(() => {
					button(container, "Run pause").click();
				});
				await settle();
				await tick(4000);
				expect(container.querySelector("[data-repair-task]")).toBeNull();
				expect(api.polls()).toBe(0);
			});
		});
	});
});
