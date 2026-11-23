"use client";

import { unwrap } from "@securefabric/client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { CopyField } from "@/components/common";
import { errorText } from "@/components/kit";
import {
	compactValues,
	defaultsFor,
	type JsonSchema,
	SchemaForm,
	validate,
} from "@/components/schema-form";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, Select } from "@/components/ui/overlay";
import { Field, Input } from "@/components/ui/primitives";
import { api } from "@/lib/api";

/**
 * Add a connection for an organization (CON-01): a credential form rendered from
 * the connector's schema, a redirect (GitHub App install), or a hosted connect
 * link to send to the customer (CON-08).
 */
export function AddConnectionDialog({
	open,
	onOpenChange,
	organizationId,
}: {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	organizationId?: string;
}) {
	const { client, env } = useEnv();
	const href = useHref();
	const router = useRouter();
	const queryClient = useQueryClient();
	const connectors = useQuery({
		queryFn: () => unwrap(api.GET("/v1/connectors")),
		queryKey: ["connectors"],
	});
	const orgs = useQuery({
		enabled: open && !organizationId,
		queryFn: () =>
			unwrap(
				client.GET("/v1/organizations", { params: { query: { limit: 500 } } })
			),
		queryKey: ["organizations", env.id, "all"],
	});
	const [org, setOrg] = useState(organizationId ?? "");
	const [vendor, setVendor] = useState("SANDBOX");
	const [identifier, setIdentifier] = useState("");
	const [creds, setCreds] = useState<Record<string, unknown>>({});
	const [opts, setOpts] = useState<Record<string, unknown>>({});
	const [errors, setErrors] = useState<Record<string, string>>({});
	const [link, setLink] = useState<string | null>(null);
	const connector = connectors.data?.find((c) => c.id === vendor);
	const redirect = connector?.auth.connect === "redirect";
	const orgId = organizationId ?? org;
	const done = async (id: string) => {
		await queryClient.invalidateQueries({ queryKey: ["connections", env.id] });
		onOpenChange(false);
		router.push(href(`/connections/${id}`));
	};
	const create = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/organizations/{organization_id}/connections", {
					body: {
						credentials: redirect ? null : compactValues(creds),
						identifier: identifier || null,
						options: compactValues(opts),
						vendor,
					},
					params: { path: { organization_id: orgId } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't create the connection", {
				description: errorText(e),
			}),
		onSuccess: async (c) => {
			if (c.authorize_url) {
				window.open(c.authorize_url, "_blank", "noopener");
				toast.info(`Finish in ${connector?.name ?? vendor}`, {
					description:
						"Install the app in the new tab. The connection activates when the vendor sends you back.",
				});
			} else {
				toast.success("Connection created", {
					description: "Verifying the credentials now.",
				});
			}
			await done(c.id);
		},
	});
	const session = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/connect_sessions", {
					body: { integrations: [vendor], organization_id: orgId },
				})
			),
		onError: (e) =>
			toast.error("Couldn't create a link", { description: errorText(e) }),
		onSuccess: (s) => setLink(s.url),
	});
	const submit = () => {
		const errs = redirect
			? {}
			: validate(connector?.credentials_schema as JsonSchema, creds);
		setErrors(errs);
		if (Object.keys(errs).length === 0 && orgId) {
			create.mutate();
		}
	};
	return (
		<Dialog
			onOpenChange={(o) => {
				setLink(null);
				onOpenChange(o);
			}}
			open={open}
		>
			<DialogContent
				description="Connect a customer's vendor tenant. Credentials are sealed before the request returns."
				footer={
					<>
						<Button
							disabled={!orgId || session.isPending}
							onClick={() => session.mutate()}
							variant="outline"
						>
							Create connect link
						</Button>
						<Button
							disabled={!orgId || create.isPending}
							onClick={submit}
							variant="primary"
						>
							{redirect
								? `Continue to ${connector?.name ?? vendor}`
								: "Create connection"}
						</Button>
					</>
				}
				title="Add connection"
			>
				<div className="grid gap-4">
					{organizationId ? null : (
						<Field
							help="The customer this connection belongs to"
							label="Organization"
						>
							<Select
								onChange={setOrg}
								options={(orgs.data?.items ?? []).map((o) => ({
									description: o.identifier,
									label: o.name,
									value: o.id,
								}))}
								placeholder="Choose an organization"
								value={org}
							/>
						</Field>
					)}
					<Field label="Connector">
						<Select
							onChange={(v) => {
								setVendor(v);
								const c = connectors.data?.find((x) => x.id === v);
								setCreds(defaultsFor(c?.credentials_schema as JsonSchema));
								setOpts({});
								setErrors({});
							}}
							options={(connectors.data ?? []).map((c) => ({
								label: c.name,
								value: c.id,
							}))}
							value={vendor}
						/>
					</Field>
					<Field
						help="Your own key for this connection (optional)"
						htmlFor="conn-ident"
						label="Identifier"
					>
						<Input
							id="conn-ident"
							onChange={(e) => setIdentifier(e.target.value)}
							value={identifier}
						/>
					</Field>
					{redirect ? (
						<p className="text-muted-foreground text-sm">
							{connector?.name} connects by installing an app: you'll be sent to
							the vendor, and the connection activates once the vendor confirms
							access. There is nothing to paste.
						</p>
					) : (
						<SchemaForm
							errors={errors}
							idPrefix="cred"
							onChange={setCreds}
							schema={connector?.credentials_schema as JsonSchema}
							values={creds}
						/>
					)}
					{link ? (
						<Field
							help="Valid for 30 minutes, single use. Send it to the customer."
							label="Connect link"
						>
							<CopyField label="Connect link" value={link} />
						</Field>
					) : null}
				</div>
			</DialogContent>
		</Dialog>
	);
}
