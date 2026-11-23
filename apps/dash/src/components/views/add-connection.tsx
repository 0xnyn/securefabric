"use client";

import { unwrap } from "@securefabric/client";
import { Button } from "@securefabric/ui/components/button";
import { Dialog, DialogContent } from "@securefabric/ui/components/dialog";
import { Field, Input } from "@securefabric/ui/components/form";
import { Select } from "@securefabric/ui/components/select";
import { EntityAvatar } from "@securefabric/ui/patterns/avatar";
import { CopyField } from "@securefabric/ui/patterns/copy";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Gated } from "@/components/domain/access";
import { ConnectorLogo } from "@/components/domain/connector-logo";
import { errorText } from "@/components/domain/query-state";
import {
	compactValues,
	defaultsFor,
	type JsonSchema,
	SchemaForm,
	validate,
} from "@/components/domain/schema-form";
import { useEnv, useHref } from "@/components/shell/env-context";
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
						"Install the app in the new tab. The connection activates when you come back.",
				});
			} else {
				toast.success("Connection added", {
					description: "We're checking the credentials now.",
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
			toast.error("Couldn't create the connect link", {
				description: errorText(e),
			}),
		onSuccess: (s) => setLink(s.url),
	});
	let submitLabel = "Add connection";
	if (create.isPending) {
		submitLabel = "Adding…";
	} else if (redirect) {
		submitLabel = `Continue to ${connector?.name ?? vendor}`;
	}
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
				description="Connect a customer's vendor account, or create a link so they can. Credentials are encrypted on save."
				footer={
					<>
						<Gated requires={{ scope: "provisioning:write" }}>
							<Button
								disabled={!orgId || session.isPending}
								onClick={() => session.mutate()}
								variant="outline"
							>
								{session.isPending ? "Creating…" : "Create connect link"}
							</Button>
						</Gated>
						<Gated requires={{ scope: "provisioning:write" }}>
							<Button
								disabled={!orgId || create.isPending}
								onClick={submit}
								variant="primary"
							>
								{submitLabel}
							</Button>
						</Gated>
					</>
				}
				title="Add connection"
			>
				<div className="grid gap-4">
					{organizationId ? null : (
						<Field
							help="The customer this connection belongs to."
							label="Organization"
						>
							<Select
								ariaLabel="Organization"
								onChange={setOrg}
								options={(orgs.data?.items ?? []).map((o) => ({
									description: o.identifier,
									label: (
										<span className="inline-flex items-center gap-2">
											<EntityAvatar name={o.name} size={16} />
											{o.name}
										</span>
									),
									value: o.id,
								}))}
								placeholder="Choose an organization"
								value={org}
							/>
						</Field>
					)}
					<Field label="Connector">
						<Select
							ariaLabel="Connector"
							onChange={(v) => {
								setVendor(v);
								const c = connectors.data?.find((x) => x.id === v);
								setCreds(defaultsFor(c?.credentials_schema as JsonSchema));
								setOpts({});
								setErrors({});
							}}
							options={(connectors.data ?? []).map((c) => ({
								label: (
									<span className="inline-flex items-center gap-2">
										<ConnectorLogo
											id={c.id}
											logo={c.logo_url}
											name={c.name}
											size={16}
										/>
										{c.name}
									</span>
								),
								value: c.id,
							}))}
							value={vendor}
						/>
					</Field>
					<Field
						help="Optional. Your own ID for this connection, shown in place of the vendor name."
						htmlFor="conn-ident"
						label="Identifier"
					>
						<Input
							id="conn-ident"
							onChange={(e) => setIdentifier(e.target.value)}
							placeholder="acme-github"
							value={identifier}
						/>
					</Field>
					{redirect ? (
						<p className="text-muted-foreground text-sm">
							{connector?.name} connects through an app install. Approve access
							in {connector?.name}, and the connection activates when you come
							back.
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
							help="Send this to your customer. It works once, for 30 minutes."
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
