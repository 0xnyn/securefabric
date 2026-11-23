"use client";

import { unwrap } from "@securefabric/client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { CopyField, PageBody, PageHeader } from "@/components/common";
import { ConfirmButton, errorText, QueryState, When } from "@/components/kit";
import { useEnv } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import {
	Badge,
	Card,
	Field,
	Input,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";

export const SCOPES = [
	"provisioning:read",
	"provisioning:write",
	"data:read",
	"jobs:execute",
	"webhooks:manage",
	"keys:manage",
	"actions:write",
] as const;

/** API keys (AUTH-03): shown once at creation, hashed at rest, revocable. */
export function KeysView() {
	const { client, env } = useEnv();
	const queryClient = useQueryClient();
	const keys = useQuery({
		queryFn: () => unwrap(client.GET("/v1/api_keys")),
		queryKey: ["keys", env.id],
	});
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
			toast.error("Couldn't revoke", { description: errorText(e) }),
		onSuccess: async () => {
			toast.success("Key revoked");
			await refresh();
		},
	});
	return (
		<>
			<PageHeader
				actions={
					<Button onClick={() => setOpen(true)} variant="primary">
						Create key
					</Button>
				}
				description={`Keys are bound to ${env.name}: send them as a Bearer token. The full key is shown once.`}
				title="API keys"
			/>
			<PageBody>
				<QueryState
					empty={{
						description: "Create a key to call the API from your backend.",
						title: "No keys",
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
									<Th>Scopes</Th>
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
												<Badge className="ml-2">revoked</Badge>
											) : null}
										</Td>
										<Td className="font-mono text-xs">{k.prefix}…</Td>
										<Td className="max-w-xs text-xs">
											{k.scopes.length === SCOPES.length
												? "all"
												: k.scopes.join(", ")}
										</Td>
										<Td>
											<When value={k.last_used_at} />
										</Td>
										<Td>
											<When value={k.created_at} />
										</Td>
										<Td className="text-right">
											{k.revoked_at ? null : (
												<ConfirmButton
													confirmLabel="Revoke key"
													description="Requests with it fail immediately."
													onConfirm={() => revoke.mutate(k.id)}
													size="xs"
													title={`Revoke "${k.name}"?`}
													variant="ghost"
												>
													Revoke
												</ConfirmButton>
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
					footer={
						<Button
							disabled={!name || scopes.length === 0 || create.isPending}
							onClick={() => create.mutate()}
							variant="primary"
						>
							Create key
						</Button>
					}
					title="Create API key"
				>
					<div className="grid gap-4">
						<Field htmlFor="key-name" label="Name">
							<Input
								id="key-name"
								onChange={(e) => setName(e.target.value)}
								placeholder="Backend (production)"
								value={name}
							/>
						</Field>
						<Field label="Scopes">
							<div className="grid gap-1.5 sm:grid-cols-2">
								{SCOPES.map((s) => (
									<label className="flex items-center gap-2 text-xs" key={s}>
										<input
											checked={scopes.includes(s)}
											onChange={(e) =>
												setScopes(
													e.target.checked
														? [...scopes, s]
														: scopes.filter((x) => x !== s)
												)
											}
											type="checkbox"
										/>
										<span className="font-mono">{s}</span>
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
					description="Copy it now. It is stored hashed and can't be shown again."
					footer={
						<Button onClick={() => setCreated(null)} variant="primary">
							Done
						</Button>
					}
					title="Your new API key"
				>
					{created ? <CopyField label="API key" value={created} /> : null}
				</DialogContent>
			</Dialog>
		</>
	);
}
