import { describe, expect, it } from "vitest";
import {
	ClientResponseError,
	createClient,
	isApiError,
	NotFoundResponseError,
	unwrap,
	ValidationResponseError,
} from "./index";

const json = (status: number, body: unknown): Response =>
	new Response(JSON.stringify(body), {
		headers: { "content-type": "application/json" },
		status,
	});

/** A client whose fetch answers every request with `response`. */
const clientReturning = (response: Response) =>
	createClient("http://api.test", { fetch: () => Promise.resolve(response) });

const TASK_ID = "0192f4a8-0000-7000-8000-000000000001";

describe("unwrap", () => {
	it("returns typed data for 2xx responses", async () => {
		const api = clientReturning(
			json(200, { queue: "default", state: "running", task_id: TASK_ID })
		);
		const task = await unwrap(
			api.GET("/api/v1/tasks/{task_id}", {
				params: { path: { task_id: TASK_ID } },
			})
		);
		expect(task.state).toBe("running");
	});

	it("maps the error envelope to NotFoundResponseError", async () => {
		const api = clientReturning(
			json(404, { error: { code: "not_found", message: "Task not found" } })
		);
		const request = unwrap(
			api.GET("/api/v1/tasks/{task_id}", {
				params: { path: { task_id: TASK_ID } },
			})
		);
		await expect(request).rejects.toBeInstanceOf(NotFoundResponseError);
		await expect(request).rejects.toMatchObject({
			code: "not_found",
			message: "Task not found",
			status: 404,
		});
	});

	it("exposes per-field validation errors", async () => {
		const api = clientReturning(
			json(422, {
				error: {
					code: "validation_failed",
					details: {
						errors: [{ loc: ["body", "tenant_id"], msg: "bad id", type: "x" }],
					},
					message: "Request validation failed",
				},
			})
		);
		const error = await unwrap(
			api.POST("/api/v1/tenants", {
				body: { admin_email: "a@b.co", tenant_id: "Bad Id" },
			})
		).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(ValidationResponseError);
		expect(isApiError(error, "validation_failed")).toBe(true);
		expect((error as ValidationResponseError).fieldErrors).toEqual({
			tenant_id: "bad id",
		});
	});

	it("falls back to a synthetic body for non-envelope errors", async () => {
		const api = clientReturning(new Response("upstream down", { status: 502 }));
		const error = await unwrap(api.GET("/health/live")).catch(
			(e: unknown) => e
		);
		expect(error).toBeInstanceOf(ClientResponseError);
		expect((error as ClientResponseError).code).toBe("http_502");
	});
});
