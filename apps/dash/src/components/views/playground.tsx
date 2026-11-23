"use client";

import { cn } from "@securefabric/ui/lib/utils";
import { Loader2Icon, PlayIcon, PlugZapIcon } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CodeBlock, CodeTabs, ProviderLogo } from "@/components/common";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button, buttonVariants } from "@/components/ui/button";
import { Select } from "@/components/ui/overlay";
import {
	Badge,
	Card,
	EmptyState,
	Input,
	Kbd,
} from "@/components/ui/primitives";
import { useSidebar } from "@/components/ui/sidebar";
import { getProvider } from "@/lib/catalog";
import {
	ENDPOINTS,
	type Endpoint,
	type Param,
	type SimResponse,
	sampleId,
	simulate,
} from "@/lib/endpoints";
import { mask } from "@/lib/format";
import { type RequestSpec, samples, sdkResource } from "@/lib/snippets";
import { logOperation } from "@/lib/store";
import type { Connection, Environment } from "@/lib/types";

const METHOD_STYLES: Record<Endpoint["method"], string> = {
	GET: "text-ds-success-text",
	PATCH: "text-ds-accent",
	POST: "text-ds-accent",
};

const OP_KIND = {
	action: "action",
	connections: "api",
	get: "api",
	list: "api",
	passthrough: "proxy",
} as const satisfies Record<Endpoint["kind"], "action" | "api" | "proxy">;

const GROUPS: Endpoint["group"][] = ["Unified models", "Actions", "Platform"];

function defaults(params: Param[] | undefined): Record<string, string> {
	const out: Record<string, string> = {};
	for (const p of params ?? []) {
		if (p.default !== undefined) {
			out[p.name] = p.default;
		}
	}
	return out;
}

function compatible(env: Environment, ep: Endpoint): Connection[] {
	if (ep.kind === "action") {
		return env.connections.filter((c) =>
			getProvider(c.provider)?.writeActions.some((w) => w.scope === ep.scope)
		);
	}
	const { model } = ep;
	if (!model) {
		return env.connections;
	}
	return env.connections.filter((c) =>
		env.integrations
			.find((i) => i.id === c.integrationId)
			?.models.includes(model)
	);
}

function resolvePath(ep: Endpoint, params: Record<string, string>): string {
	return ep.path.replace("{id}", params.id || "{id}");
}

function queryFor(
	ep: Endpoint,
	params: Record<string, string>
): Record<string, string> {
	const q: Record<string, string> = {};
	for (const p of ep.params) {
		const v = params[p.name];
		if (p.name !== "id" && v) {
			q[p.name] = v;
		}
	}
	return q;
}

function ParamInput({
	param,
	value,
	onChange,
}: {
	param: Param;
	value: string;
	onChange: (v: string) => void;
}) {
	if (param.type === "multi") {
		const selected = value ? value.split(",") : [];
		return (
			<div className="flex flex-wrap gap-1.5">
				{param.options?.map((o) => {
					const on = selected.includes(o);
					return (
						<button
							aria-pressed={on}
							className={cn(
								"h-7 rounded-md border px-2.5 text-xs transition-colors",
								on
									? "border-foreground bg-foreground text-background"
									: "border-border hover:bg-muted"
							)}
							key={o}
							onClick={() =>
								onChange(
									(on
										? selected.filter((s) => s !== o)
										: [...selected, o]
									).join(",")
								)
							}
							type="button"
						>
							{o}
						</button>
					);
				})}
			</div>
		);
	}
	if (param.options) {
		return (
			<Select
				ariaLabel={param.name}
				onChange={onChange}
				options={[
					{ label: "Any", value: "" },
					...param.options.map((o) => ({ label: o, value: o })),
				].filter((o) => !(param.default && o.value === ""))}
				size="sm"
				value={value}
			/>
		);
	}
	return (
		<Input
			aria-label={param.name}
			className="text-code h-8 font-mono"
			onChange={(e) => onChange(e.target.value)}
			placeholder={
				param.type === "datetime" ? "2026-11-01T00:00:00Z" : param.default
			}
			type={param.type === "number" ? "number" : "text"}
			value={value}
		/>
	);
}

function ParamRow({
	param,
	value,
	onChange,
}: {
	param: Param;
	value: string;
	onChange: (v: string) => void;
}) {
	return (
		<div className="border-border grid gap-2 border-b px-5 py-3 last:border-b-0 sm:grid-cols-[11rem_minmax(0,1fr)] sm:items-start">
			<div className="grid gap-0.5">
				<span className="text-code flex items-center gap-1.5 font-mono">
					{param.name}
					{param.required ? <span className="text-destructive">*</span> : null}
				</span>
				<span className="text-muted-foreground text-xs">
					{param.description}
				</span>
			</div>
			<ParamInput onChange={onChange} param={param} value={value} />
		</div>
	);
}

function statusTone(status: number): string {
	if (status < 300) {
		return "bg-ds-success/10 text-ds-success-text";
	}
	if (status < 500) {
		return "bg-destructive/10 text-destructive";
	}
	return "bg-destructive/10 text-destructive";
}

function ResponsePanel({
	response,
	loading,
}: {
	response: SimResponse | null;
	loading: boolean;
}) {
	if (loading) {
		return (
			<Card className="text-muted-foreground flex min-h-80 items-center justify-center gap-2 text-sm">
				<Loader2Icon className="size-4 animate-spin" />
				Sending request…
			</Card>
		);
	}
	if (!response) {
		return (
			<Card className="text-muted-foreground flex min-h-80 flex-col items-center justify-center gap-2 px-6 text-center text-sm">
				<PlayIcon className="size-5" />
				<p>
					Press <span className="text-foreground font-medium">Send</span> or{" "}
					<Kbd>⌘</Kbd> <Kbd>Enter</Kbd> to call the API.
				</p>
				<p className="text-xs">
					Requests run against this environment's connections and show up in
					Logs and Metrics.
				</p>
			</Card>
		);
	}
	return (
		<CodeBlock
			code={JSON.stringify(response.body, null, 2)}
			json
			maxHeight="36rem"
			title={
				<span className="flex items-center gap-3 font-sans">
					<span
						className={cn(
							"rounded px-1.5 py-0.5 font-mono font-medium",
							statusTone(response.status)
						)}
					>
						{response.status}
					</span>
					<span>{response.durationMs}ms</span>
					<span className="hidden font-mono sm:inline">
						{response.headers["x-request-id"]}
					</span>
				</span>
			}
		/>
	);
}

function HeadersCard({
	needsConnection,
	options,
	connectionId,
	onConnection,
}: {
	needsConnection: boolean;
	options: Connection[];
	connectionId: string;
	onConnection: (id: string) => void;
}) {
	const { env } = useEnv();
	return (
		<Card>
			<div className="border-border border-b px-5 py-3 text-sm font-medium">
				Headers
			</div>
			<div className="border-border grid gap-2 border-b px-5 py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:items-center">
				<span className="text-code font-mono">X-API-Key</span>
				<span className="text-code text-muted-foreground truncate font-mono">
					{mask(env.keys.secret)}
				</span>
			</div>
			{needsConnection ? (
				<div className="grid gap-2 px-5 py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:items-center">
					<span className="text-code font-mono">X-Connection-Id</span>
					<Select
						ariaLabel="Connection"
						onChange={onConnection}
						options={options.map((c) => ({
							description: `${c.id} · ${getProvider(c.provider)?.name}`,
							label: (
								<span className="flex items-center gap-2">
									<ProviderLogo provider={c.provider} size={16} />
									{c.customer.orgName}
									{c.sandbox ? <Badge tone="accent">Sandbox</Badge> : null}
								</span>
							),
							value: c.id,
						}))}
						size="sm"
						value={connectionId}
					/>
				</div>
			) : null}
		</Card>
	);
}

function RequestSections({
	endpoint,
	params,
	body,
	setParams,
	setBody,
}: {
	endpoint: Endpoint;
	params: Record<string, string>;
	body: Record<string, string>;
	setParams: (p: Record<string, string>) => void;
	setBody: (b: Record<string, string>) => void;
}) {
	return (
		<>
			{endpoint.params.length > 0 ? (
				<Card>
					<div className="border-border border-b px-5 py-3 text-sm font-medium">
						{endpoint.kind === "list" ? "Query parameters" : "Path parameters"}
					</div>
					{endpoint.params.map((p) => (
						<ParamRow
							key={p.name}
							onChange={(v) => setParams({ ...params, [p.name]: v })}
							param={p}
							value={params[p.name] ?? ""}
						/>
					))}
				</Card>
			) : null}
			{endpoint.body ? (
				<Card>
					<div className="border-border flex items-center justify-between border-b px-5 py-3 text-sm font-medium">
						Body
						{endpoint.scope ? (
							<Badge className="font-mono">{endpoint.scope}</Badge>
						) : null}
					</div>
					{endpoint.body.map((p) => (
						<ParamRow
							key={p.name}
							onChange={(v) => setBody({ ...body, [p.name]: v })}
							param={p}
							value={body[p.name] ?? ""}
						/>
					))}
				</Card>
			) : null}
		</>
	);
}

/**
 * The endpoint list, as a picker, for when the sidebar's list isn't on
 * screen: the sidebar collapsed to icons, or a phone, where it's a sheet.
 */
function EndpointSwitcher({
	current,
	onPick,
}: {
	current: string;
	onPick: (e: Endpoint) => void;
}) {
	const { isMobile, state } = useSidebar();
	if (!isMobile && state === "expanded") {
		return null;
	}
	return (
		<Select
			ariaLabel="Endpoint"
			className="sm:w-72 sm:shrink-0"
			onChange={(id) => {
				const next = ENDPOINTS.find((e) => e.id === id);
				if (next) {
					onPick(next);
				}
			}}
			options={GROUPS.flatMap((g) =>
				ENDPOINTS.filter((e) => e.group === g).map((e) => ({
					label: (
						<span className="flex items-center gap-2">
							<span
								className={cn(
									"text-2xs w-10 shrink-0 font-mono font-medium",
									METHOD_STYLES[e.method]
								)}
							>
								{e.method}
							</span>
							<span className="truncate">{e.title}</span>
						</span>
					),
					value: e.id,
				}))
			)}
			value={current}
		/>
	);
}

/** The endpoint a link asked for, else the first one the linked connection
 * can answer, else the first. */
function startEndpoint(
	env: Environment,
	requested: string | null,
	preferred: Connection | undefined
): Endpoint {
	return (
		ENDPOINTS.find((e) => e.id === requested) ??
		ENDPOINTS.find(
			(e) => e.model && preferred && compatible(env, e).includes(preferred)
		) ??
		(ENDPOINTS[0] as Endpoint)
	);
}

export function PlaygroundView() {
	const { env } = useEnv();
	const href = useHref();
	const search = useSearchParams();
	const router = useRouter();
	const pathname = usePathname();
	const preferred = env.connections.find(
		(c) => c.id === search.get("connection")
	);
	const urlEndpoint = search.get("endpoint");
	const startEp = startEndpoint(env, urlEndpoint, preferred);
	const [endpointId, setEndpointId] = useState(startEp.id);
	const endpoint = ENDPOINTS.find((e) => e.id === endpointId) ?? startEp;
	const options = compatible(env, endpoint);
	const [connectionId, setConnectionId] = useState(
		preferred?.id ?? options[0]?.id ?? ""
	);
	const conn = options.find((c) => c.id === connectionId) ?? options[0] ?? null;
	const [params, setParams] = useState<Record<string, string>>(() => ({
		...defaults(startEp.params),
		id: sampleId(preferred ?? options[0] ?? null, startEp.model),
	}));
	const [body, setBody] = useState<Record<string, string>>(
		defaults(startEp.body)
	);
	const [response, setResponse] = useState<SimResponse | null>(null);
	const [loading, setLoading] = useState(false);

	const applyEndpoint = (ep: Endpoint): void => {
		setEndpointId(ep.id);
		const nextConns = compatible(env, ep);
		const nextConn =
			nextConns.find((c) => c.id === conn?.id) ?? nextConns[0] ?? null;
		setConnectionId(nextConn?.id ?? "");
		setParams({ ...defaults(ep.params), id: sampleId(nextConn, ep.model) });
		setBody(defaults(ep.body));
		setResponse(null);
	};

	// The sidebar and ⌘K link to `?endpoint=`. Following one while the page
	// is open switches the endpoint in place (React's "adjust state during
	// render" pattern, so there is no render with the old endpoint).
	const [seenEndpoint, setSeenEndpoint] = useState(urlEndpoint);
	if (urlEndpoint !== seenEndpoint) {
		setSeenEndpoint(urlEndpoint);
		const next = ENDPOINTS.find((e) => e.id === urlEndpoint);
		if (next && next.id !== endpointId) {
			applyEndpoint(next);
		}
	}

	const pickEndpoint = (ep: Endpoint): void => {
		applyEndpoint(ep);
		const query = new URLSearchParams(search);
		query.set("endpoint", ep.id);
		router.replace(`${pathname}?${query.toString()}`, { scroll: false });
	};

	const needsConnection = endpoint.kind !== "connections";
	const spec: RequestSpec = {
		body: endpoint.body ? body : undefined,
		connectionId: needsConnection
			? (conn?.id ?? "conn_XXXXXXXXXXXX")
			: undefined,
		method: endpoint.method,
		path: resolvePath(endpoint, params),
		query: queryFor(endpoint, params),
		sdk:
			endpoint.kind === "list" || endpoint.kind === "connections"
				? [sdkResource(endpoint.path), "list"]
				: undefined,
		secretKey: env.keys.secret,
	};

	const send = (): void => {
		setLoading(true);
		setResponse(null);
		const result = simulate(
			env,
			endpoint,
			needsConnection ? conn : null,
			params,
			body
		);
		setTimeout(() => {
			setResponse(result);
			setLoading(false);
			logOperation(env.slug, needsConnection ? (conn?.id ?? null) : null, {
				action: `${endpoint.method} ${spec.path}`,
				durationMs: result.durationMs,
				method: endpoint.method,
				path: spec.path,
				records: result.records,
				status: result.status < 400 ? "success" : "failed",
				statusCode: result.status,
				type: OP_KIND[endpoint.kind],
			});
		}, result.durationMs + 120);
	};

	useEffect(() => {
		const onKey = (e: KeyboardEvent): void => {
			if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
				send();
			}
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	});

	return (
		<div className="grid w-full gap-6 px-4 py-7 sm:px-8">
			<div className="grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-5">
				{/* The switcher sits at the end of the title row, above Send, so it
				    reads as "change what this request is" when the sidebar's
				    list is out of view. */}
				<div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
					<div className="grid min-w-0 gap-1">
						<h1 className="tracking-heading text-2xl font-semibold">
							{endpoint.title}
						</h1>
						<p className="text-muted-foreground text-sm">
							{endpoint.description}
						</p>
					</div>
					<EndpointSwitcher current={endpoint.id} onPick={pickEndpoint} />
				</div>

				<div className="flex flex-col gap-2 sm:flex-row">
					<div className="border-border bg-background text-code flex h-10 min-w-0 flex-1 items-center gap-3 rounded-md border px-3 font-mono">
						<span
							className={cn("font-semibold", METHOD_STYLES[endpoint.method])}
						>
							{endpoint.method}
						</span>
						<span className="truncate">
							<span className="text-muted-foreground">
								https://api.securefabric.dev
							</span>
							{spec.path}
						</span>
					</div>
					<Button
						className="h-10 px-5"
						disabled={loading || (needsConnection && !conn)}
						onClick={send}
						variant="primary"
					>
						{loading ? <Loader2Icon className="animate-spin" /> : <PlayIcon />}
						Send
					</Button>
				</div>

				{needsConnection && options.length === 0 ? (
					<EmptyState
						action={
							<Link
								className={buttonVariants({ variant: "primary" })}
								href={href("/connections?new=1")}
							>
								Add a sandbox connection
							</Link>
						}
						description={
							endpoint.model
								? `No connection in ${env.name} provides this model yet. A sandbox connection takes a few seconds.`
								: "Add a connection first."
						}
						icon={<PlugZapIcon className="size-4" />}
						title="No compatible connection"
					/>
				) : null}

				<div className="grid gap-5 xl:grid-cols-2">
					<div className="grid min-w-0 content-start gap-5">
						<HeadersCard
							connectionId={conn?.id ?? ""}
							needsConnection={needsConnection}
							onConnection={(id) => {
								setConnectionId(id);
								setParams((p) => ({
									...p,
									id: sampleId(
										options.find((c) => c.id === id) ?? null,
										endpoint.model
									),
								}));
							}}
							options={options}
						/>
						<RequestSections
							body={body}
							endpoint={endpoint}
							params={params}
							setBody={setBody}
							setParams={setParams}
						/>
						<CodeTabs samples={samples(spec)} />
					</div>
					<div className="min-w-0">
						<ResponsePanel loading={loading} response={response} />
					</div>
				</div>
			</div>
		</div>
	);
}
