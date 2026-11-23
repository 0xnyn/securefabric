"use client";

import { ClientResponseError } from "@securefabric/client";
import { Button } from "@securefabric/ui/components/button";
import { EmptyState } from "@securefabric/ui/components/empty-state";
import { Skeleton } from "@securefabric/ui/primitives/skeleton";
import { RefreshCwIcon } from "lucide-react";

/** A human sentence for any error, with the API's request id when there is one. */
export function errorText(error: unknown): string {
	if (error instanceof ClientResponseError) {
		const fields = error.errors
			.map((e) => `${e.field}: ${e.message}`)
			.join("; ");
		return [
			error.message,
			fields,
			error.requestId ? `(${error.requestId})` : "",
		]
			.filter(Boolean)
			.join(" ");
	}
	return error instanceof Error ? error.message : String(error);
}

/** Loading, error and empty states for a query, in one place. */
export function QueryState({
	query,
	empty,
	children,
	rows = 4,
}: {
	query: {
		isPending: boolean;
		isError: boolean;
		error: unknown;
		refetch: () => unknown;
	};
	empty?: {
		when: boolean;
		title: string;
		description: React.ReactNode;
		action?: React.ReactNode;
		icon?: React.ReactNode;
	};
	children: React.ReactNode;
	rows?: number;
}) {
	if (query.isPending) {
		return (
			<div className="grid gap-2">
				{Array.from({ length: rows }, (_, i) => (
					// biome-ignore lint/suspicious/noArrayIndexKey: placeholders have no identity
					<Skeleton className="h-10" key={i} />
				))}
			</div>
		);
	}
	if (query.isError) {
		return (
			<EmptyState
				action={
					<Button onClick={() => query.refetch()} size="sm" variant="outline">
						<RefreshCwIcon /> Try again
					</Button>
				}
				description={errorText(query.error)}
				title="Couldn't load this data"
			/>
		);
	}
	if (empty?.when) {
		return (
			<EmptyState
				action={empty.action}
				description={empty.description}
				icon={empty.icon}
				title={empty.title}
			/>
		);
	}
	return <>{children}</>;
}
