"use client";

import { unwrap } from "@securefabric/client";
import { Badge } from "@securefabric/ui/components/badge";
import { Button } from "@securefabric/ui/components/button";
import { Card } from "@securefabric/ui/components/card";
import { Dialog, DialogContent } from "@securefabric/ui/components/dialog";
import { Field, Input } from "@securefabric/ui/components/form";
import { Table, Td, Th, Tr } from "@securefabric/ui/components/table";
import { Tooltip } from "@securefabric/ui/components/tooltip";
import { PersonAvatar } from "@securefabric/ui/patterns/avatar";
import { CopyField } from "@securefabric/ui/patterns/copy";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { TriangleAlertIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Gated } from "@/components/domain/access";
import { ConfirmButton } from "@/components/domain/confirm-button";
import { errorText, QueryState } from "@/components/domain/query-state";
import { When } from "@/components/domain/when";
import { useEnv } from "@/components/shell/env-context";
import type { Requirement } from "@/lib/access";
import type { ApiKey, Member } from "@/lib/types";

export const SCOPES = [
	"provisioning:read",
	"provisioning:write",
	"data:read",
	"jobs:execute",
	"webhooks:manage",
	"keys:manage",
	"actions:write",
] as const;

/** Each scope in plain words, with one line on what it allows. */
export const SCOPE_LABELS: Record<string, { label: string; help: string }> = {
	"actions:write": {
		help: "Change a finding's state at the vendor.",
		label: "Run write-back actions",
	},
	"data:read": {
		help: "Read findings, resources and events.",
		label: "Read data",
	},
	"jobs:execute": {
		help: "Start syncs on connections.",
		label: "Run syncs",
	},
	"keys:manage": {
		help: "Create and revoke API keys.",
		label: "Manage API keys",
	},
	"provisioning:read": {
		help: "View organizations, integrations and connections.",
		label: "View setup",
	},
	"provisioning:write": {
		help: "Create, change and delete organizations, integrations and connections.",
		label: "Manage setup",
	},
	"webhooks:manage": {
		help: "Add, change and delete webhook endpoints.",
		label: "Manage webhooks",
	},
};

export function scopeLabel(scope: string): string {
	return SCOPE_LABELS[scope]?.label ?? scope;
}

const MANAGE: Requirement = { scope: "keys:manage" };

/** API keys (AUTH-03): shown once at creation, hashed at rest, revocable. */
export function KeysView() {
	const { client, env } = useEnv();
	const queryClient = useQueryClient();
	const keys = useQuery({
		queryFn: () => unwrap(client.GET("/v1/api_keys")),
		queryKey: ["keys", env.id],
	});
	const creatorOf = useCreators(keys.data ?? []);
	const [open, setOpen] = useState(false);
	const [name, setName] = useState("");
	const [scopes, setScopes] = useState<string[]>([...SCOPES]);
	const [created, setCreated] = useState<string | null>(null);
	const refresh = () =>
		queryClient.invalidateQueries({ queryKey: ["keys", env.id] });
	const create = useMutation({
		mutationFn: () =>
			unwrap(
				client.POST("/v1/api_keys", {
					body: { name, scopes },
					headers: { "Idempotency-Key": crypto.randomUUID() },
				})
			),
		onError: (e) =>
			toast.error("Couldn't create the key", { description: errorText(e) }),
		onSuccess: async (k) => {
			setOpen(false);
			setName("");
			setCreated(k.key);
			await refresh();
		},
	});
	const revoke = useMutation({
		mutationFn: (id: string) =>
			unwrap(
				client.DELETE("/v1/api_keys/{key_id}", {
					params: { path: { key_id: id } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't revoke the key", { description: errorText(e) }),
		onSuccess: async () => {
			toast.success("Key revoked");
			await refresh();
		},
	});
	const createButton = (size?: "sm") => (
		<Gated requires={MANAGE}>
			<Button onClick={() => setOpen(true)} size={size} variant="primary">
				Create key
			</Button>
		</Gated>
	);
	return (
		<>
			<PageHeader
				actions={createButton()}
				description={`Keys your backend uses to call the API in ${env.name}.`}
				title="API keys"
			/>
			<PageBody>
				<QueryState
					empty={{
						action: createButton("sm"),
						description: "Create a key to call the API from your backend.",
						title: "No API keys yet",
						when: (keys.data ?? []).length === 0,
					}}
					query={keys}
				>
					<Card>
						<Table>
							<thead>
								<Tr>
									<Th>Name</Th>
									<Th>Key</Th>
									<Th>Access</Th>
									<Th>Created by</Th>
									<Th>Last used</Th>
									<Th>Created</Th>
									<Th />
								</Tr>
							</thead>
							<tbody>
								{keys.data?.map((k) => (
									<Tr
										className={k.revoked_at ? "opacity-50" : undefined}
										key={k.id}
									>
										<Td className="font-medium">
											{k.name}
											{k.revoked_at ? (
												<Badge className="ml-2">Revoked</Badge>
											) : null}
										</Td>
										<Td className="font-mono text-xs">{k.prefix}…</Td>
										<Td className="max-w-xs">
											<ScopeList scopes={k.scopes} />
										</Td>
										<Td>{creatorOf(k.created_by)}</Td>
										<Td>
											<When value={k.last_used_at} />
										</Td>
										<Td>
											<When value={k.created_at} />
										</Td>
										<Td className="text-right">
											{k.revoked_at ? null : (
												<Gated requires={MANAGE}>
													<ConfirmButton
														confirmLabel="Revoke key"
														description="Requests that use this key start failing within a minute. You can't undo this."
														disabled={
															revoke.isPending && revoke.variables === k.id
														}
														onConfirm={() => revoke.mutate(k.id)}
														size="xs"
														title={`Revoke “${k.name}”?`}
														variant="ghost"
													>
														{revoke.isPending && revoke.variables === k.id
															? "Revoking…"
															: "Revoke key"}
													</ConfirmButton>
												</Gated>
											)}
										</Td>
									</Tr>
								))}
							</tbody>
						</Table>
					</Card>
				</QueryState>
			</PageBody>
			<Dialog onOpenChange={setOpen} open={open}>
				<DialogContent
					description="You'll see the full key only once, right after you create it."
					footer={
						<>
							<Button onClick={() => setOpen(false)}>Cancel</Button>
							<Button
								disabled={!name || scopes.length === 0 || create.isPending}
								onClick={() => create.mutate()}
								variant="primary"
							>
								{create.isPending ? "Creating…" : "Create key"}
							</Button>
						</>
					}
					title="Create API key"
				>
					<div className="grid gap-4">
						<Field
							help="Name it after where it's used."
							htmlFor="key-name"
							label="Name"
						>
							<Input
								id="key-name"
								onChange={(e) => setName(e.target.value)}
								placeholder="Backend (production)"
								value={name}
							/>
						</Field>
						<Field help="Give the key only the access it needs." label="Access">
							<div className="grid gap-2">
								{SCOPES.map((s) => (
									<label className="flex items-start gap-2 text-sm" key={s}>
										<input
											checked={scopes.includes(s)}
											className="mt-1"
											onChange={(e) =>
												setScopes(
													e.target.checked
														? [...scopes, s]
														: scopes.filter((x) => x !== s)
												)
											}
											type="checkbox"
										/>
										<span className="grid">
											<span>
												{scopeLabel(s)}{" "}
												<span className="text-muted-foreground font-mono text-xs">
													{s}
												</span>
											</span>
											<span className="text-muted-foreground text-xs">
												{SCOPE_LABELS[s]?.help}
											</span>
										</span>
									</label>
								))}
							</div>
						</Field>
					</div>
				</DialogContent>
			</Dialog>
			<Dialog
				onOpenChange={(o) => (o ? null : setCreated(null))}
				open={created !== null}
			>
				<DialogContent
					description="Store it in your secrets manager, then send it as a Bearer token."
					footer={
						<Button onClick={() => setCreated(null)} variant="primary">
							I've saved the key
						</Button>
					}
					title="Copy your new API key"
				>
					<div className="grid gap-4">
						<div
							className="border-ds-severity-high/40 bg-ds-severity-high/10 flex items-start gap-2 rounded-md border px-3 py-2 text-sm"
							role="alert"
						>
							<TriangleAlertIcon className="mt-0.5 size-4 shrink-0" />
							<span>
								<strong className="font-medium">Shown once.</strong> We only
								store a hash, so you can't see this key again after you close
								this window.
							</span>
						</div>
						{created ? <CopyField label="API key" value={created} /> : null}
					</div>
				</DialogContent>
			</Dialog>
		</>
	);
}

/** The key's scopes in words; "Full access" when it has all of them. */
function ScopeList({ scopes }: { scopes: string[] }) {
	if (SCOPES.every((s) => scopes.includes(s))) {
		return <span className="text-sm">Full access</span>;
	}
	if (scopes.length === 0) {
		return <span className="text-muted-foreground">—</span>;
	}
	return (
		<div className="flex flex-wrap gap-1">
			{scopes.map((s) => (
				<Tooltip content={<span className="font-mono">{s}</span>} key={s}>
					<Badge>{scopeLabel(s)}</Badge>
				</Tooltip>
			))}
		</div>
	);
}

/**
 * Who created each key: a teammate (from GET /v1/members, which needs a
 * signed-in session, so not in dev mode) or another API key.
 */
function useCreators(keys: ApiKey[]) {
	const { client, devMode } = useEnv();
	const members = useQuery({
		enabled: !devMode,
		queryFn: () => unwrap(client.GET("/v1/members")),
		queryKey: ["members"],
		staleTime: 60_000,
	});
	const people = new Map<string, Member>(
		(members.data ?? []).map((m) => [m.user_id, m])
	);
	const byId = new Map(keys.map((k) => [k.id, k]));
	return (createdBy: string | null): React.ReactNode => {
		if (!createdBy) {
			return <span className="text-muted-foreground">—</span>;
		}
		const person = people.get(createdBy);
		if (person) {
			return (
				<span className="inline-flex items-center gap-2 whitespace-nowrap">
					<PersonAvatar seed={person.email} size={20} />
					<Tooltip content={person.email}>
						<span>{person.name ?? person.email}</span>
					</Tooltip>
				</span>
			);
		}
		const key = byId.get(createdBy);
		if (key) {
			return (
				<span className="text-muted-foreground whitespace-nowrap">
					API key “{key.name}”
				</span>
			);
		}
		return <span className="text-muted-foreground">—</span>;
	};
}
