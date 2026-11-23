"use client";

import { unwrap } from "@securefabric/client";
import { Button } from "@securefabric/ui/components/button";
import { Card } from "@securefabric/ui/components/card";
import { Dialog, DialogContent } from "@securefabric/ui/components/dialog";
import { Field, Input } from "@securefabric/ui/components/form";
import { Table, Td, Th, Tr } from "@securefabric/ui/components/table";
import { num } from "@securefabric/ui/lib/format";
import { EntityAvatar } from "@securefabric/ui/patterns/avatar";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PlusIcon } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Gated } from "@/components/domain/access";
import { Pager, useCursorStack } from "@/components/domain/pager";
import { errorText, QueryState } from "@/components/domain/query-state";
import { When } from "@/components/domain/when";
import { useAccess, useEnv, useHref } from "@/components/shell/env-context";
import { useDebounce } from "@/hooks/use-debounce";
import { AddConnectionDialog } from "./add-connection";
import { ConnectionsTable } from "./connections";

/**
 * A page-header button (default size, so it lines up with its neighbours)
 * that asks before doing something it can't undo. kit's ConfirmButton only
 * comes in table-row sizes.
 */
export function HeaderConfirmButton({
	title,
	description,
	confirmLabel,
	onConfirm,
	disabled,
	children,
}: {
	title: string;
	description: React.ReactNode;
	confirmLabel: string;
	onConfirm: () => void;
	disabled?: boolean;
	children: React.ReactNode;
}) {
	const [open, setOpen] = useState(false);
	return (
		<>
			<Button
				disabled={disabled}
				onClick={() => setOpen(true)}
				variant="outline"
			>
				{children}
			</Button>
			<Dialog onOpenChange={setOpen} open={open}>
				<DialogContent
					description={description}
					footer={
						<>
							<Button onClick={() => setOpen(false)}>Cancel</Button>
							<Button
								onClick={() => {
									setOpen(false);
									onConfirm();
								}}
								variant="destructive"
							>
								{confirmLabel}
							</Button>
						</>
					}
					title={title}
				>
					{null}
				</DialogContent>
			</Dialog>
		</>
	);
}

export function OrganizationsView() {
	const { client, env } = useEnv();
	const access = useAccess();
	const href = useHref();
	const params = useSearchParams();
	const [search, setSearch] = useState("");
	const q = useDebounce(search, 250);
	const pages = useCursorStack();
	const [open, setOpen] = useState(
		params.get("new") === "1" && access.can("provisioning:write")
	);
	const orgs = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/organizations", {
					params: {
						query: { cursor: pages.cursor, limit: 50, search: q || undefined },
					},
				})
			),
		queryKey: ["organizations", env.id, q, pages.cursor],
	});
	const addButton = (
		<Gated requires={{ scope: "provisioning:write" }}>
			<Button onClick={() => setOpen(true)} variant="primary">
				<PlusIcon /> Add organization
			</Button>
		</Gated>
	);
	return (
		<>
			<PageHeader
				actions={
					<>
						<Input
							aria-label="Search organizations"
							className="w-56"
							onChange={(e) => {
								pages.reset();
								setSearch(e.target.value);
							}}
							placeholder="Search organizations"
							type="search"
							value={search}
						/>
						{addButton}
					</>
				}
				description="Your customers, each with its own connections and synced data."
				title="Organizations"
			/>
			<PageBody>
				<QueryState
					empty={
						q
							? {
									action: (
										<Button
											onClick={() => {
												pages.reset();
												setSearch("");
											}}
											size="sm"
											variant="outline"
										>
											Clear search
										</Button>
									),
									description: `No name or identifier matches “${q}”.`,
									title: "No matching organizations",
									when: (orgs.data?.items.length ?? 0) === 0,
								}
							: {
									action: (
										<Gated requires={{ scope: "provisioning:write" }}>
											<Button
												onClick={() => setOpen(true)}
												size="sm"
												variant="primary"
											>
												<PlusIcon /> Add organization
											</Button>
										</Gated>
									),
									description:
										"Add one for each customer, then connect their vendor accounts.",
									title: "No organizations yet",
									when: (orgs.data?.items.length ?? 0) === 0,
								}
					}
					query={orgs}
				>
					<Card>
						<Table>
							<thead>
								<Tr>
									<Th>Name</Th>
									<Th>Identifier</Th>
									<Th className="text-right">Connections</Th>
									<Th>Created</Th>
								</Tr>
							</thead>
							<tbody>
								{orgs.data?.items.map((o) => (
									<Tr className="hover:bg-muted/40" key={o.id}>
										<Td>
											<Link
												className="inline-flex items-center gap-3 font-medium hover:underline"
												href={href(`/organizations/${o.id}`)}
											>
												<EntityAvatar name={o.name} size={24} />
												{o.name}
											</Link>
										</Td>
										<Td className="font-mono text-xs">{o.identifier}</Td>
										<Td className="text-right tabular-nums">
											{num(o.connection_count)}
										</Td>
										<Td>
											<When value={o.created_at} />
										</Td>
									</Tr>
								))}
							</tbody>
						</Table>
					</Card>
					<Pager
						count={orgs.data?.items.length}
						hasNext={Boolean(orgs.data?.next_cursor)}
						onNext={() => pages.next(orgs.data?.next_cursor)}
						onPrev={pages.prev}
						page={pages.page}
					/>
				</QueryState>
			</PageBody>
			<CreateOrganizationDialog onOpenChange={setOpen} open={open} />
		</>
	);
}

function CreateOrganizationDialog({
	open,
	onOpenChange,
}: {
	open: boolean;
	onOpenChange: (o: boolean) => void;
}) {
	const { client, env } = useEnv();
	const href = useHref();
	const router = useRouter();
	const queryClient = useQueryClient();
	const [name, setName] = useState("");
	const [identifier, setIdentifier] = useState("");
	const create = useMutation({
		mutationFn: () =>
			unwrap(client.POST("/v1/organizations", { body: { identifier, name } })),
		onError: (e) =>
			toast.error("Couldn't add the organization", {
				description: errorText(e),
			}),
		onSuccess: async (o) => {
			toast.success("Organization added");
			await queryClient.invalidateQueries({
				queryKey: ["organizations", env.id],
			});
			onOpenChange(false);
			router.push(href(`/organizations/${o.id}`));
		},
	});
	return (
		<Dialog onOpenChange={onOpenChange} open={open}>
			<DialogContent
				description="Add one organization for each of your customers."
				footer={
					<>
						<Button onClick={() => onOpenChange(false)}>Cancel</Button>
						<Gated requires={{ scope: "provisioning:write" }}>
							<Button
								disabled={!(name && identifier) || create.isPending}
								onClick={() => create.mutate()}
								variant="primary"
							>
								{create.isPending ? "Adding…" : "Add organization"}
							</Button>
						</Gated>
					</>
				}
				title="Add organization"
			>
				<div className="grid gap-4">
					<Field htmlFor="org-name" label="Name">
						<Input
							id="org-name"
							onChange={(e) => setName(e.target.value)}
							placeholder="Acme Corp"
							value={name}
						/>
					</Field>
					<Field
						help="Your own ID for this customer. It must be unique in this environment."
						htmlFor="org-ident"
						label="Identifier"
					>
						<Input
							className="font-mono"
							id="org-ident"
							onChange={(e) => setIdentifier(e.target.value)}
							placeholder="acme-corp"
							value={identifier}
						/>
					</Field>
				</div>
			</DialogContent>
		</Dialog>
	);
}

export function OrganizationView({ id }: { id: string }) {
	const { client, env } = useEnv();
	const href = useHref();
	const router = useRouter();
	const queryClient = useQueryClient();
	const [add, setAdd] = useState(false);
	const org = useQuery({
		queryFn: () =>
			unwrap(
				client.GET("/v1/organizations/{organization_id}", {
					params: { path: { organization_id: id } },
				})
			),
		queryKey: ["organizations", env.id, id],
	});
	const remove = useMutation({
		mutationFn: () =>
			unwrap(
				client.DELETE("/v1/organizations/{organization_id}", {
					params: { path: { organization_id: id } },
				})
			),
		onError: (e) =>
			toast.error("Couldn't delete the organization", {
				description: errorText(e),
			}),
		onSuccess: async () => {
			toast.success("Organization deleted");
			await queryClient.invalidateQueries({
				queryKey: ["organizations", env.id],
			});
			router.push(href("/organizations"));
		},
	});
	return (
		<QueryState query={org}>
			{org.data ? (
				<>
					<PageHeader
						actions={
							<>
								<Button
									render={<Link href={href(`/findings?org=${id}`)} />}
									variant="outline"
								>
									View findings
								</Button>
								<Gated requires={{ scope: "provisioning:write" }}>
									<HeaderConfirmButton
										confirmLabel="Delete organization"
										description="Delete its connections first. You can't undo this."
										disabled={remove.isPending}
										onConfirm={() => remove.mutate()}
										title={`Delete “${org.data.name}”?`}
									>
										{remove.isPending ? "Deleting…" : "Delete organization"}
									</HeaderConfirmButton>
								</Gated>
								<Gated requires={{ scope: "provisioning:write" }}>
									<Button onClick={() => setAdd(true)} variant="primary">
										<PlusIcon /> Add connection
									</Button>
								</Gated>
							</>
						}
						description={
							<span className="font-mono">
								{org.data.identifier} · {org.data.id}
							</span>
						}
						title={
							<span className="flex items-center gap-3">
								<EntityAvatar name={org.data.name} size={32} />
								{org.data.name}
							</span>
						}
					/>
					<PageBody>
						<ConnectionsTable onAdd={() => setAdd(true)} organizationId={id} />
					</PageBody>
					<AddConnectionDialog
						onOpenChange={setAdd}
						open={add}
						organizationId={id}
					/>
				</>
			) : null}
		</QueryState>
	);
}
