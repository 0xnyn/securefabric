"use client";

import { PlugZapIcon, PlusIcon } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { PageBody, PageHeader } from "@/components/common";
import { useEnv, useHref } from "@/components/shell/env-context";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/primitives";
import { useNuqsAdapter } from "@/lib/store/adapters/nuqs";
import { DataTableStoreProvider } from "@/lib/store/provider/DataTableStoreProvider";
import { AddConnectionDialog } from "./add-connection";
import { ConnectionsTable } from "./connections/connections-table";
import { filterSchema } from "./connections/schema";

/**
 * Filters live in the URL, so the sidebar's views (`?status=attention`,
 * `?kind=sandbox`) and ⌘K open a filtered list, and a pasted link reopens it.
 */
export function ConnectionsView() {
	const { env } = useEnv();
	const href = useHref();
	const router = useRouter();
	const params = useSearchParams();
	const adapter = useNuqsAdapter(filterSchema.definition, {
		id: "connections",
	});
	const [adding, setAdding] = useState(params.get("new") === "1");

	const setOpen = (open: boolean): void => {
		setAdding(open);
		if (!open && params.get("new")) {
			router.replace(href("/connections"));
		}
	};

	return (
		<>
			<PageHeader
				actions={
					<Button onClick={() => setAdding(true)} variant="primary">
						<PlusIcon />
						Add connection
					</Button>
				}
				description="One connection per customer account in a tool. Pass its ID in the X-Connection-Id header to read that customer's data."
				title="Connections"
			/>
			<PageBody>
				{env.connections.length === 0 ? (
					<EmptyState
						action={
							<Button onClick={() => setAdding(true)} variant="primary">
								<PlusIcon />
								Add connection
							</Button>
						}
						description="Connect a sandbox account to read realistic data now, or send a customer a Connect link."
						icon={<PlugZapIcon className="size-4" />}
						title="No connections yet"
					/>
				) : (
					<DataTableStoreProvider adapter={adapter}>
						{/* Keyed by environment: switching resets selection and paging. */}
						<ConnectionsTable
							connections={env.connections}
							key={env.slug}
							tableId={`connections:${env.slug}`}
						/>
					</DataTableStoreProvider>
				)}
			</PageBody>
			<AddConnectionDialog
				initialIntegration={params.get("integration")}
				onOpenChange={setOpen}
				open={adding}
			/>
		</>
	);
}
