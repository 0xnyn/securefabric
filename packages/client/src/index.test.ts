import { describe, expect, it } from "vitest";
import {
	ClientResponseError,
	createClient,
	isApiError,
	NotFoundResponseError,
	TooManyRequestsResponseError,
	unwrap,
	ValidationResponseError,
} from "./index";

const problem = (
	status: number,
	body: unknown,
	headers: Record<string, string> = {}
): Response =>
	new Response(JSON.stringify(body), {
		headers: { "content-type": "application/problem+json", ...headers },
		status,
	});

const json = (status: number, body: unknown): Response =>
	new Response(JSON.stringify(body), {
		headers: { "content-type": "application/json" },
		status,
	});

const clientReturning = (response: Response) =>
	createClient("http://api.test", { fetch: () => Promise.resolve(response) });

const ORG = "0192f4a8-0000-7000-8000-000000000001";

const p = (status: number, code: string, extra: object = {}) => ({
	code,
	detail: `detail for ${code}`,
	errors: [],
	request_id: "req_123",
	status,
	title: "Title",
	type: `https://docs.securefabric.dev/errors/${code}`,
	...extra,
});

describe("unwrap", () => {
	it("returns typed data for 2xx responses", async () => {
		const api = clientReturning(
			json(200, {
				connection_count: 0,
				id: ORG,
				identifier: "acme",
				name: "Acme",
			})
		);
		const org = await unwrap(
			api.GET("/v1/organizations/{organization_id}", {
				params: { path: { organization_id: ORG } },
			})
		);
		expect(org.identifier).toBe("acme");
	});

	it("maps problem details to NotFoundResponseError", async () => {
		const api = clientReturning(problem(404, p(404, "organization_not_found")));
		const request = unwrap(
			api.GET("/v1/organizations/{organization_id}", {
				params: { path: { organization_id: ORG } },
			})
		);
		await expect(request).rejects.toBeInstanceOf(NotFoundResponseError);
		await expect(request).rejects.toMatchObject({
			code: "organization_not_found",
			message: "detail for organization_not_found",
			requestId: "req_123",
			status: 404,
		});
	});

	it("exposes per-field errors", async () => {
		const api = clientReturning(
			problem(
				422,
				p(422, "invalid_credentials", {
					errors: [{ field: "credentials.api_key", message: "pattern failed" }],
				})
			)
		);
		const error = await unwrap(
			api.POST("/v1/organizations", { body: { identifier: "x", name: "x" } })
		).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(ValidationResponseError);
		expect(isApiError(error, "invalid_credentials")).toBe(true);
		expect((error as ValidationResponseError).fieldErrors).toEqual({
			"credentials.api_key": "pattern failed",
		});
	});

	it("reads Retry-After on 429", async () => {
		const api = clientReturning(
			problem(429, p(429, "rate_limited"), { "retry-after": "7" })
		);
		const error = await unwrap(api.GET("/v1/me")).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(TooManyRequestsResponseError);
		expect((error as TooManyRequestsResponseError).retryAfter).toBe(7);
	});

	it("falls back to a synthetic problem for non-problem errors", async () => {
		const api = clientReturning(
			new Response("upstream down", {
				headers: { "x-request-id": "req_9" },
				status: 502,
			})
		);
		const error = await unwrap(api.GET("/health/live")).catch(
			(e: unknown) => e
		);
		expect(error).toBeInstanceOf(ClientResponseError);
		expect((error as ClientResponseError).code).toBe("http_502");
		expect((error as ClientResponseError).requestId).toBe("req_9");
	});
});

describe("createClient", () => {
	it("sends the bearer token", async () => {
		let seen: Request | undefined;
		const api = createClient("http://api.test", {
			fetch: (req) => {
				seen = req;
				return Promise.resolve(json(200, {}));
			},
			token: "sfk_test_us_abc",
		});
		await api.GET("/v1/me");
		expect(seen?.headers.get("authorization")).toBe("Bearer sfk_test_us_abc");
	});
});
