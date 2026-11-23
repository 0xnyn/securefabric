import createOpenAPIFetchClient, {
	type Client as FetchClient,
	type HeadersOptions,
} from "openapi-fetch";

import type { components, operations, paths } from "./v1.js";

const HTTP_NOT_FOUND = 404;
const HTTP_UNPROCESSABLE = 422;
const HTTP_TOO_MANY_REQUESTS = 429;

/**
 * A typed fetch client for the SecureFabric API. Paths, params, bodies and
 * responses (errors included) come from `paths` in `./v1`, which is generated
 * from the FastAPI app's OpenAPI schema: `pnpm generate`.
 *
 * ```ts
 * const api = createClient("http://localhost:8000");
 * const org = await unwrap(
 *   api.GET("/v1/organizations/{organization_id}", {
 *     params: { path: { organization_id } },
 *   })
 * );
 * org.identifier;
 * ```
 */
export const createClient = (
	baseUrl: string,
	options: {
		token?: string;
		headers?: HeadersOptions;
		/** Custom fetch, e.g. Next's server fetch or a stub in tests. */
		fetch?: (input: Request) => Promise<Response>;
	} = {}
): FetchClient<paths> & { baseUrl: string } => {
	const { token, headers, fetch } = options;
	return {
		...createOpenAPIFetchClient<paths>({
			baseUrl,
			...(fetch ? { fetch } : {}),
			headers: {
				...headers,
				...(token ? { Authorization: `Bearer ${token}` } : {}),
			},
		}),
		baseUrl,
	};
};

export type Client = ReturnType<typeof createClient>;

export type schemas = components["schemas"];

/**
 * The RFC 9457 problem details body of every non-2xx response (API-06):
 * `{ type, title, status, detail, code, request_id, errors[] }`.
 */
export type Problem = schemas["Problem"];
export type FieldError = schemas["FieldError"];

export class ClientResponseError extends Error {
	readonly body: Problem;
	readonly response: Response;

	constructor(body: Problem, response: Response) {
		super(
			body.detail ||
				body.title ||
				`Request failed with status ${response.status}`
		);
		this.name = "ClientResponseError";
		this.body = body;
		this.response = response;
	}

	/** The API's stable error code, e.g. `not_found` or `scope_missing`. */
	get code(): string {
		return this.body.code;
	}

	get status(): number {
		return this.response.status;
	}

	/** The request id to quote to support (also in the X-Request-Id header). */
	get requestId(): string | null {
		return this.body.request_id ?? this.response.headers.get("x-request-id");
	}

	/** Per-field problems, e.g. `[{ field: "credentials.api_key", message }]`. */
	get errors(): FieldError[] {
		return this.body.errors ?? [];
	}

	/** Field problems keyed by field path, for form errors (first one wins). */
	get fieldErrors(): Partial<Record<string, string>> {
		const out: Partial<Record<string, string>> = {};
		for (const e of this.errors) {
			if (!(e.field in out)) {
				out[e.field] = e.message;
			}
		}
		return out;
	}
}

export class NotFoundResponseError extends ClientResponseError {
	constructor(body: Problem, response: Response) {
		super(body, response);
		this.name = "NotFoundResponseError";
	}
}

export class ValidationResponseError extends ClientResponseError {
	constructor(body: Problem, response: Response) {
		super(body, response);
		this.name = "ValidationResponseError";
	}
}

export class TooManyRequestsResponseError extends ClientResponseError {
	constructor(body: Problem, response: Response) {
		super(body, response);
		this.name = "TooManyRequestsResponseError";
	}

	/** Seconds to wait, from Retry-After. */
	get retryAfter(): number | null {
		const v = this.response.headers.get("retry-after");
		return v ? Number(v) : null;
	}
}

const isProblem = (value: unknown): value is Problem =>
	typeof value === "object" &&
	value !== null &&
	"code" in value &&
	"status" in value &&
	typeof (value as { code: unknown }).code === "string";

const toProblem = (error: unknown, response: Response): Problem =>
	isProblem(error)
		? { errors: [], ...error }
		: {
				code: `http_${response.status}`,
				detail: typeof error === "string" ? error : response.statusText,
				errors: [],
				request_id: response.headers.get("x-request-id"),
				status: response.status,
				title: response.statusText || "Error",
				type: "about:blank",
			};

const errorFor = (body: Problem, response: Response): ClientResponseError => {
	switch (response.status) {
		case HTTP_NOT_FOUND:
			return new NotFoundResponseError(body, response);
		case HTTP_UNPROCESSABLE:
			return new ValidationResponseError(body, response);
		case HTTP_TOO_MANY_REQUESTS:
			return new TooManyRequestsResponseError(body, response);
		default:
			return new ClientResponseError(body, response);
	}
};

interface FetchResult {
	data?: unknown;
	error?: unknown;
	response: Response;
}

/**
 * Await an `api.GET/POST/...` call and return its typed data, or throw a
 * `ClientResponseError` subclass. Made for TanStack Query `queryFn`s and
 * `mutationFn`s.
 */
export const unwrap = async <R extends FetchResult>(
	request: Promise<R>
): Promise<NonNullable<R["data"]>> => {
	const { data, error, response } = await request;
	if (error !== undefined || !response.ok) {
		throw errorFor(toProblem(error, response), response);
	}
	// 204s have no body; callers of those endpoints ignore the value.
	return data as NonNullable<R["data"]>;
};

/** Narrow a caught error to one the API raised on purpose, optionally by code. */
export const isApiError = (
	error: unknown,
	code?: string
): error is ClientResponseError =>
	error instanceof ClientResponseError &&
	(code === undefined || error.code === code);

export type { Middleware } from "openapi-fetch";
export type { components, operations, paths } from "./v1.js";

/** Request body of an operation, e.g. `RequestBody<"organizations:create_organization">`. */
export type RequestBody<K extends keyof operations> = operations[K] extends {
	requestBody: { content: { "application/json": infer B } };
}
	? B
	: never;
