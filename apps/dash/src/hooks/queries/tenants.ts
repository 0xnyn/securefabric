import { type RequestBody, type schemas, unwrap } from "@securefabric/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "./keys";

/** Exactly the pydantic `ProvisionTenantParams` model, via the OpenAPI schema. */
export type ProvisionTenantInput = RequestBody<"tenants:provision_tenant">;
export type TenantPlan = NonNullable<schemas["ProvisionTenantParams"]["plan"]>;
export type TaskAccepted = schemas["TaskAccepted"];

/** Enqueue the `provision-tenant` durable workflow. Resolves with its task. */
export const useProvisionTenant = () => {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: ({
			idempotencyKey,
			...body
		}: ProvisionTenantInput & { idempotencyKey?: string }) =>
			unwrap(
				api.POST("/api/v1/tenants", {
					body,
					params: {
						header: idempotencyKey ? { "idempotency-key": idempotencyKey } : {},
					},
				})
			),
		onSuccess: () =>
			queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all }),
	});
};
