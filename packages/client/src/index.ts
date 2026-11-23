import createOpenAPIFetchClient, { type HeadersOptions } from "openapi-fetch";

import type { components, operations, paths } from "./v1";

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
 * const task = await unwrap(
 *   api.GET("/api/v1/tasks/{task_id}", { params: { path: { task_id } } })
 * );
 * task.state; // "pending" | "running" | ... straight from absurd_sdk's Literal
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
) => {
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

/** The `{ error: { code, message, details? } }` body of every non-2xx response. */
export type ErrorResponse = schemas["ErrorResponse"];
export type ErrorBody = schemas["ErrorBody"];

export class ClientResponseError extends Error {
	readonly body: ErrorBody;
	readonly response: Response;

	constructor(body: ErrorBody, response: Response) {
		super(body.message || `Request failed with status ${response.status}`);
		this.name = "ClientResponseError";
		this.body = body;
		this.response = response;
	}

	/** The API's stable error code, e.g. `not_found` or `validation_failed`. */
	get code(): string {
		return this.body.code;
	}

	get status(): number {
		return this.response.status;
	}
}

export class NotFoundResponseError extends ClientResponseError {
	constructor(body: ErrorBody, response: Response) {
		super(body, response);
		this.name = "NotFoundResponseError";
	}
}

export interface ValidationIssue {
	loc: (string | number)[];
	msg: string;
	type: string;
}

export class ValidationResponseError extends ClientResponseError {
	constructor(body: ErrorBody, response: Response) {
		super(body, response);
		this.name = "ValidationResponseError";
	}

	/** Pydantic's per-field errors, e.g. `[{ loc: ["body", "tenant_id"], msg, type }]`. */
	get issues(): ValidationIssue[] {
		const errors = this.body.details?.errors;
		return Array.isArray(errors) ? (errors as ValidationIssue[]) : [];
	}

	/** Issues keyed by field name (the last `loc` segment), for form errors. */
	get fieldErrors(): Partial<Record<string, string>> {
		const out: Partial<Record<string, string>> = {};
		for (const issue of this.issues) {
			const field = issue.loc.at(-1);
			if (field !== undefined && !(String(field) in out)) {
				out[String(field)] = issue.msg;
			}
		}
		return out;
	}
}

export class TooManyRequestsResponseError extends ClientResponseError {
	constructor(body: ErrorBody, response: Response) {
		super(body, response);
		this.name = "TooManyRequestsResponseError";
	}
}

const isErrorResponse = (value: unknown): value is ErrorResponse =>
	typeof value === "object" &&
	value !== null &&
	"error" in value &&
	typeof (value as { error: unknown }).error === "object" &&
	(value as { error: unknown }).error !== null;

const toErrorBody = (error: unknown, response: Response): ErrorBody =>
	isErrorResponse(error)
		? error.error
		: {
				code: `http_${response.status}`,
				message: typeof error === "string" ? error : response.statusText,
			};

const errorFor = (body: ErrorBody, response: Response): ClientResponseError => {
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
		throw errorFor(toErrorBody(error, response), response);
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
export type { components, operations, paths } from "./v1";

/** Request body of an operation, e.g. `RequestBody<"tenants:provision_tenant">`. */
export type RequestBody<K extends keyof operations> = operations[K] extends {
	requestBody: { content: { "application/json": infer B } };
}
	? B
	: never;
