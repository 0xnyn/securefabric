"use client";

import { unwrap } from "@securefabric/client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { PageBody, PageHeader } from "@/components/common";
import {
	errorText,
	Pager,
	QueryState,
	useCursorStack,
	When,
} from "@/components/kit";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/overlay";
import {
	Card,
	Field,
	Input,
	Table,
	Td,
	Th,
	Tr,
} from "@/components/ui/primitives";
import { useDebounce } from "@/hooks/use-debounce";
import { AddConnectionDialog } from "./add-connection";
import { ConnectionsTable } from "./connections";

export function OrganizationsView() {
	const { client, env } = useEnv();
	const href = useHref();
	const params = useSearchParams();
	const [search, setSearch] = useState("");
	const q = useDebounce(search, 250);
	const pages = useCursorStack();
	const [open, setOpen] = useState(params.get("new") === "1");
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
	return (
		<>
			<PageHeader
				actions={
					<>
						<Input
							className="w-56"
							onChange={(e) => {
								pages.reset();
								setSearch(e.target.value);
							}}
							placeholder="Search name or identifier"
							value={search}
						/>
						<Button onClick={() => setOpen(true)} variant="primary">
							Add organization
						</Button>
					</>
				}
				description="Your customers. Each owns its connections; data reads can be scoped to one with X-ORGANIZATION-ID."
				title="Organizations"
			/>
			<PageBody>
				<QueryState
					empty={{
						action: (
							<Button onClick={() => setOpen(true)} size="sm" variant="primary">
								Add organization
							</Button>
						),
						description:
							"Create one per customer, keyed by your own identifier.",
						title: q ? "No matches" : "No organizations yet",
						when: (orgs.data?.items.length ?? 0) === 0,
					}}
					query={orgs}
				>
					<Card>
						<Table>
							<thead>
								<Tr>
									<Th>Name</Th>
									<Th>Identifier</Th>
									<Th>Connections</Th>
									<Th>Created</Th>
								</Tr>
							</thead>
							<tbody>
								{orgs.data?.items.map((o) => (
									<Tr className="hover:bg-muted/40" key={o.id}>
										<Td>
											<Link
												className="font-medium hover:underline"
												href={href(`/organizations/${o.id}`)}
											>
												{o.name}
											</Link>
										</Td>
										<Td className="font-mono text-xs">{o.identifier}</Td>
										<Td>{o.connection_count}</Td>
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
			toast.error("Couldn't create the organization", {
				description: errorText(e),
			}),
		onSuccess: async (o) => {
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
				footer={
					<Button
						disabled={!(name && identifier) || create.isPending}
						onClick={() => create.mutate()}
						variant="primary"
					>
						Create
					</Button>
				}
				title="Add organization"
			>
				<div className="grid gap-4">
					<Field htmlFor="org-name" label="Name">
						<Input
							id="org-name"
							onChange={(e) => setName(e.target.value)}
							value={name}
						/>
					</Field>
					<Field
						help="Your own id for this customer, unique in the environment"
						htmlFor="org-ident"
						label="Identifier"
					>
						<Input
							className="font-mono"
							id="org-ident"
							onChange={(e) => setIdentifier(e.target.value)}
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
			toast.error("Couldn't delete", { description: errorText(e) }),
		onSuccess: () => router.push(href("/organizations")),
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
									Findings
								</Button>
								<Button onClick={() => remove.mutate()} variant="outline">
									Delete
								</Button>
								<Button onClick={() => setAdd(true)} variant="primary">
									Add connection
								</Button>
							</>
						}
						description={
							<span className="font-mono">
								{org.data.identifier} · {org.data.id}
							</span>
						}
						title={org.data.name}
					/>
					<PageBody>
						<ConnectionsTable organizationId={id} />
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
