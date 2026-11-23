// @vitest-environment jsdom

import { createClient } from "@securefabric/client";
import { TooltipProvider } from "@securefabric/ui/components/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EnvContext } from "@/components/shell/env-context";
import type { Connection, Environment, Me } from "@/lib/types";
import { ConnectionsTable } from "./connections";

(
	globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }
).IS_REACT_ACT_ENVIRONMENT = true;

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

// The public catalogue (id → name), answered without a network.
vi.mock("@/lib/api", async () => {
	const client = await import("@securefabric/client");
	return {
		api: client.createClient("http://test/api/sf", {
			fetch: () =>
				Promise.resolve(
					new Response(
						JSON.stringify([{ id: "GITHUB", logo_url: null, name: "GitHub" }]),
						{ headers: { "content-type": "application/json" }, status: 200 }
					)
				),
		}),
	};
});

const ENV: Environment = {
	created_at: null,
	id: "11111111-1111-1111-1111-111111111111",
	is_production: false,
	name: "Development",
	settings: {},
	slug: "dev",
};

const ME = {
	environments: [ENV],
	kind: "api_key",
	needs_onboarding: false,
} as unknown as Me;

function connection(id: string, health: string, state = "ACTIVE"): Connection {
	return {
		authorization: null,
		authorize_url: null,
		connection_config: {},
		connector_version: "1.0.0",
		created_at: "2026-11-20T10:00:00.000Z",
		deleted_at: null,
		direction: "read",
		health: {
			description: null,
			details: null,
			name: health,
			resolution_owner: null,
			status: "OK",
		},
		health_changed_at: null,
		id,
		identifier: `acme-${id.slice(0, 4)}`,
		integration_id: "i",
		is_active: state === "ACTIVE",
		is_sandbox: false,
		metadata: {},
		oauth2_authorize_url: null,
		options: {},
		organization_id: "22222222-2222-2222-2222-222222222222",
		pending_detail: null,
		refresh_interval_secs: null,
		state,
		streams: null,
		tags: {},
		updated_at: new Date().toISOString(),
		vendor: "GITHUB",
	} as Connection;
}

/** A stub API: records every request, answers connections and organizations. */
function stubApi(
	pages: Record<string, { items: Connection[]; next_cursor: string | null }>
) {
	const requests: URL[] = [];
	const fetchStub = (req: Request) => {
		const url = new URL(req.url);
		requests.push(url);
		const json = (body: unknown) =>
			Promise.resolve(
				new Response(JSON.stringify(body), {
					headers: { "content-type": "application/json" },
					status: 200,
				})
			);
		if (url.pathname.endsWith("/v1/organizations")) {
			return json({
				items: [
					{
						id: "22222222-2222-2222-2222-222222222222",
						identifier: "acme",
						name: "Acme Corp",
					},
				],
				next_cursor: null,
				previous_cursor: null,
			});
		}
		const page = pages[url.searchParams.get("cursor") ?? "first"] ?? {
			items: [],
			next_cursor: null,
		};
		return json({ ...page, previous_cursor: null });
	};
	return {
		client: createClient("http://test/api/sf", { fetch: fetchStub }),
		requests,
	};
}

describe("<ConnectionsTable>", () => {
	let container: HTMLDivElement;
	let root: Root;
	beforeEach(() => {
		container = document.createElement("div");
		document.body.append(container);
		root = createRoot(container);
	});
	afterEach(() => {
		act(() => root.unmount());
		container.remove();
	});

	async function render(
		api: ReturnType<typeof stubApi>,
		{ onAdd, scopes = [] }: { onAdd?: () => void; scopes?: string[] } = {}
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
								devMode: true,
								env: ENV,
								environments: [ENV],
								me: { ...ME, scopes } as Me,
							}}
						>
							<ConnectionsTable onAdd={onAdd} />
						</EnvContext>
					</TooltipProvider>
				</QueryClientProvider>
			);
		});
		await act(() => new Promise((r) => setTimeout(r, 20)));
	}

	const rows = () => [...container.querySelectorAll("tbody tr")];

	it("lists connections with their organization, state and health", async () => {
		const api = stubApi({
			first: {
				items: [
					connection("aaaaaaaa-0000-0000-0000-000000000001", "HEALTHY"),
					connection("bbbbbbbb-0000-0000-0000-000000000002", "UNAUTHORIZED"),
				],
				next_cursor: null,
			},
		});
		await render(api);
		expect(rows()).toHaveLength(2);
		expect(rows()[0]?.textContent).toContain("Acme Corp");
		expect(rows()[0]?.textContent).toContain("GitHub");
		expect(rows()[0]?.textContent).toContain("Active");
		expect(rows()[0]?.textContent).toContain("Healthy");
		expect(rows()[1]?.textContent).toContain("Unauthorized");
		expect(
			container.querySelector(
				"a[href='/dev/connections/aaaaaaaa-0000-0000-0000-000000000001']"
			)
		).not.toBeNull();
		const list = api.requests.find((u) =>
			u.pathname.endsWith("/v1/connections")
		);
		expect(list?.searchParams.get("limit")).toBe("50");
		expect(list?.searchParams.has("cursor")).toBe(false);
	});

	it("pages with the keyset cursor and comes back", async () => {
		const api = stubApi({
			c2: {
				items: [connection("cccccccc-0000-0000-0000-000000000003", "HEALTHY")],
				next_cursor: null,
			},
			first: {
				items: [connection("aaaaaaaa-0000-0000-0000-000000000001", "HEALTHY")],
				next_cursor: "c2",
			},
		});
		await render(api);
		const next = container.querySelector<HTMLButtonElement>(
			"button[aria-label='Next page']"
		);
		const prev = container.querySelector<HTMLButtonElement>(
			"button[aria-label='Previous page']"
		);
		expect(prev?.disabled).toBe(true);
		await act(() => {
			next?.click();
		});
		await act(() => new Promise((r) => setTimeout(r, 20)));
		expect(
			api.requests.some((u) => u.searchParams.get("cursor") === "c2")
		).toBe(true);
		expect(rows()[0]?.textContent).toContain("acme-cccc");
		expect(container.textContent).toContain("Page 2");
		await act(() => {
			container
				.querySelector<HTMLButtonElement>("button[aria-label='Previous page']")
				?.click();
		});
		await act(() => new Promise((r) => setTimeout(r, 20)));
		expect(rows()[0]?.textContent).toContain("acme-aaaa");
	});

	const addButton = () =>
		[...container.querySelectorAll<HTMLButtonElement>("button")].find((b) =>
			b.textContent?.includes("Add connection")
		);

	it("shows the empty state with an add action", async () => {
		const onAdd = vi.fn();
		await render(stubApi({ first: { items: [], next_cursor: null } }), {
			onAdd,
			scopes: ["provisioning:read", "provisioning:write"],
		});
		expect(container.textContent).toContain("No connections yet");
		expect(addButton()?.disabled).toBe(false);
		await act(() => {
			addButton()?.click();
		});
		expect(onAdd).toHaveBeenCalled();
	});

	it("disables the add action without provisioning:write", async () => {
		await render(stubApi({ first: { items: [], next_cursor: null } }), {
			onAdd: () => undefined,
			scopes: ["provisioning:read"],
		});
		expect(addButton()?.disabled).toBe(true);
	});
});
