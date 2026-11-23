"use client";

import { useQuery } from "@tanstack/react-query";
import { SendIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { CodeBlock, PageBody, PageHeader } from "@/components/common";
import { QueryState } from "@/components/kit";
import { useEnv } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/overlay";
import {
	Badge,
	Card,
	Field,
	Input,
	Textarea,
} from "@/components/ui/primitives";
import { API_URL, PROXY_BASE } from "@/lib/api";

/*
 * The request console: pick any operation from the live OpenAPI document,
 * fill its parameters, and send it with the credentials this dashboard uses
 * (through the same-origin proxy, so no key ever reaches the browser).
 */

interface OaParam {
	description?: string;
	in: "path" | "query" | "header" | "cookie";
	name: string;
	required?: boolean;
}

interface OaOperation {
	operationId?: string;
	parameters?: OaParam[];
	requestBody?: { content?: Record<string, { schema?: unknown }> };
	summary?: string;
	tags?: string[];
}

interface Op {
	bodySchema: unknown;
	hasBody: boolean;
	id: string;
	method: string;
	params: OaParam[];
	path: string;
	summary: string;
	tag: string;
}

interface OpenApi {
	components?: { schemas?: Record<string, unknown> };
	paths: Record<string, Record<string, OaOperation>>;
}

const METHODS = ["get", "post", "put", "patch", "delete"];
const SKIP_HEADERS = new Set([
	"idempotency-key",
	"x-environment-id",
	"authorization",
]);

export function operationsOf(doc: OpenApi): Op[] {
	const out: Op[] = [];
	for (const [path, item] of Object.entries(doc.paths)) {
		if (!path.startsWith("/v1/") || path.startsWith("/v1/connect/")) {
			continue;
		}
		for (const method of METHODS) {
			const op = item[method];
			if (!op) {
				continue;
			}
			const content = op.requestBody?.content ?? {};
			out.push({
				bodySchema: content["application/json"]?.schema,
				hasBody: Boolean(op.requestBody),
				id: `${method.toUpperCase()} ${path}`,
				method: method.toUpperCase(),
				params: (op.parameters ?? []).filter(
					(p) => p.in !== "cookie" && !SKIP_HEADERS.has(p.name.toLowerCase())
				),
				path,
				summary: op.summary ?? op.operationId ?? "",
				tag: op.tags?.[0] ?? "other",
			});
		}
	}
	return out;
}

function placeholder(s: Record<string, unknown>): unknown {
	switch (s.type) {
		case "array":
			return [];
		case "string":
			return Array.isArray(s.enum) ? s.enum[0] : "";
		case "integer":
		case "number":
			return 0;
		case "boolean":
			return false;
		default:
			return null;
	}
}

/** A starting body from a schema: required properties with placeholder values. */
export function skeleton(root: unknown, doc: OpenApi): unknown {
	const schemas = doc.components?.schemas ?? {};
	const walk = (schema: unknown, depth: number): unknown => {
		if (!schema || typeof schema !== "object" || depth > 4) {
			return null;
		}
		const s = schema as Record<string, unknown>;
		if (typeof s.$ref === "string") {
			return walk(schemas[s.$ref.split("/").at(-1) ?? ""], depth + 1);
		}
		if (Array.isArray(s.anyOf)) {
			return walk(
				(s.anyOf as Record<string, unknown>[]).find((x) => x.type !== "null"),
				depth + 1
			);
		}
		if (s.default !== undefined) {
			return s.default;
		}
		if (s.type !== "object") {
			return placeholder(s);
		}
		const props = (s.properties ?? {}) as Record<string, unknown>;
		const required = new Set((s.required as string[] | undefined) ?? []);
		return Object.fromEntries(
			Object.entries(props)
				.filter(([k]) => required.has(k))
				.map(([k, v]) => [k, walk(v, depth + 1)])
		);
	};
	return walk(root, 0);
}

/** Path, query and header values for an operation, from the form. */
export function buildRequest(
	op: Op,
	values: Record<string, string>
): { path: string; headers: Record<string, string> } {
	let { path } = op;
	const query = new URLSearchParams();
	const headers: Record<string, string> = {};
	for (const p of op.params) {
		const v = values[`${p.in}:${p.name}`];
		if (!v) {
			continue;
		}
		if (p.in === "path") {
			path = path.replace(`{${p.name}}`, encodeURIComponent(v));
		} else if (p.in === "query") {
			query.set(p.name, v);
		} else {
			headers[p.name] = v;
		}
	}
	const qs = query.toString();
	return { headers, path: qs ? `${path}?${qs}` : path };
}

function pretty(text: string): string {
	try {
		return JSON.stringify(JSON.parse(text), null, 2);
	} catch {
		return text;
	}
}

async function sendRequest(
	op: Op,
	request: { path: string; headers: Record<string, string> },
	body: string,
	environmentId: string
): Promise<Result> {
	const started = performance.now();
	const headers: Record<string, string> = {
		...request.headers,
		"X-Environment-Id": environmentId,
	};
	if (op.method !== "GET") {
		headers["Idempotency-Key"] = crypto.randomUUID();
	}
	if (op.hasBody) {
		headers["Content-Type"] = "application/json";
	}
	try {
		const r = await fetch(`${PROXY_BASE}${request.path}`, {
			body: op.hasBody && body ? body : undefined,
			headers,
			method: op.method,
		});
		return {
			body: pretty(await r.text()),
			ms: Math.round(performance.now() - started),
			requestId: r.headers.get("x-request-id"),
			status: r.status,
		};
	} catch (e) {
		return {
			body: String(e),
			ms: Math.round(performance.now() - started),
			requestId: null,
			status: 0,
		};
	}
}

function shellQuote(s: string): string {
	return `'${s.replaceAll("'", "'\\''")}'`;
}

export function buildCurl(
	method: string,
	url: string,
	headers: Record<string, string>,
	body: string | null
): string {
	const lines = [
		`curl -X ${method} ${shellQuote(url)}`,
		`  -H "Authorization: Bearer $SECUREFABRIC_API_KEY"`,
	];
	for (const [k, v] of Object.entries(headers)) {
		lines.push(`  -H ${shellQuote(`${k}: ${v}`)}`);
	}
	if (body) {
		lines.push(
			`  -H 'Content-Type: application/json'`,
			`  -d ${shellQuote(body)}`
		);
	}
	return lines.join(" \\\n");
}

interface Result {
	body: string;
	ms: number;
	requestId: string | null;
	status: number;
}

const WHITESPACE = /\s+/gu;

function ParamField({
	param: p,
	value,
	onChange,
}: {
	param: OaParam;
	value: string;
	onChange: (v: string) => void;
}) {
	return (
		<Field
			help={p.description}
			htmlFor={`p-${p.in}-${p.name}`}
			label={
				<span className="flex items-center gap-2">
					<span className="font-mono">{p.name}</span>
					<Badge>{p.in}</Badge>
					{p.required ? <Badge tone="warn">required</Badge> : null}
				</span>
			}
		>
			<Input
				className="font-mono text-xs"
				id={`p-${p.in}-${p.name}`}
				onChange={(e) => onChange(e.target.value)}
				value={value}
			/>
		</Field>
	);
}

function ResponsePanel({ result }: { result: Result | null }) {
	if (!result) {
		return (
			<Card className="p-5">
				<p className="text-muted-foreground text-sm">
					The response appears here.
				</p>
			</Card>
		);
	}
	const ok = result.status >= 200 && result.status < 300;
	return (
		<Card className="grid content-start gap-3 p-5">
			<div className="flex flex-wrap items-center gap-2 text-sm">
				<Badge tone={ok ? "ok" : "error"}>
					{result.status || "network error"}
				</Badge>
				<span className="text-muted-foreground">{result.ms} ms</span>
				{result.requestId ? (
					<span className="text-muted-foreground font-mono text-xs">
						{result.requestId}
					</span>
				) : null}
			</div>
			<pre className="bg-ds-shell max-h-[36rem] overflow-auto rounded-md p-3 font-mono text-xs">
				{result.body}
			</pre>
		</Card>
	);
}

export function PlaygroundView() {
	const { env } = useEnv();
	const doc = useQuery({
		queryFn: async () => {
			const r = await fetch(`${PROXY_BASE}/openapi.json`);
			if (!r.ok) {
				throw new Error(`openapi.json: HTTP ${r.status}`);
			}
			return (await r.json()) as OpenApi;
		},
		queryKey: ["openapi"],
		staleTime: Number.POSITIVE_INFINITY,
	});
	const ops = useMemo(
		() => (doc.data ? operationsOf(doc.data) : []),
		[doc.data]
	);
	const [opId, setOpId] = useState("GET /v1/connections");
	const op = ops.find((o) => o.id === opId) ?? ops[0];
	const [values, setValues] = useState<Record<string, string>>({});
	const [body, setBody] = useState<string>("");
	const [result, setResult] = useState<Result | null>(null);
	const [sending, setSending] = useState(false);
	const choose = (id: string) => {
		setOpId(id);
		setValues({});
		setResult(null);
		const next = ops.find((o) => o.id === id);
		setBody(
			next?.hasBody && doc.data
				? JSON.stringify(skeleton(next.bodySchema, doc.data), null, 2)
				: ""
		);
	};
	const request = useMemo(
		() => (op ? buildRequest(op, values) : null),
		[op, values]
	);
	const send = async () => {
		if (!(op && request)) {
			return;
		}
		setSending(true);
		setResult(await sendRequest(op, request, body, env.id));
		setSending(false);
	};
	const missing =
		op?.params.filter((p) => p.required && !values[`${p.in}:${p.name}`]) ?? [];
	return (
		<>
			<PageHeader
				description="Send any API request with this dashboard's credentials. Operations come from the live OpenAPI document."
				title="Request console"
			/>
			<PageBody>
				<QueryState query={doc}>
					{op && request ? (
						<div className="grid gap-6 xl:grid-cols-2">
							<div className="grid content-start gap-4">
								<Field label="Operation">
									<Select
										onChange={choose}
										options={ops.map((o) => ({
											description: o.summary,
											label: `${o.method} ${o.path}`,
											value: o.id,
										}))}
										value={op.id}
									/>
								</Field>
								{op.summary ? (
									<p className="text-muted-foreground text-sm">{op.summary}</p>
								) : null}
								{op.params.map((p) => (
									<ParamField
										key={`${p.in}:${p.name}`}
										onChange={(v) =>
											setValues({ ...values, [`${p.in}:${p.name}`]: v })
										}
										param={p}
										value={values[`${p.in}:${p.name}`] ?? ""}
									/>
								))}
								{op.hasBody ? (
									<Field htmlFor="pg-body" label="Body (JSON)">
										<Textarea
											className="font-mono text-xs"
											id="pg-body"
											onChange={(e) => setBody(e.target.value)}
											rows={10}
											value={body}
										/>
									</Field>
								) : null}
								<div>
									<Button
										disabled={sending || missing.length > 0}
										onClick={send}
										variant="primary"
									>
										<SendIcon /> Send
									</Button>
								</div>
								<div>
									<CodeBlock
										code={buildCurl(
											op.method,
											`${API_URL}${request.path}`,
											request.headers,
											op.hasBody ? body.replace(WHITESPACE, " ") : null
										)}
										title="curl"
									/>
								</div>
							</div>
							<ResponsePanel result={result} />
						</div>
					) : null}
				</QueryState>
			</PageBody>
		</>
	);
}
