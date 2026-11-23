"use client";

import { EmptyState } from "@securefabric/ui/components/empty-state";
import { Tooltip } from "@securefabric/ui/components/tooltip";
import { PageBody, PageHeader } from "@securefabric/ui/patterns/page";
import { LockKeyholeIcon } from "lucide-react";
import { cloneElement, isValidElement } from "react";
import { useAccess } from "@/components/shell/env-context";
import { deniedReason, type Requirement } from "@/lib/access";

/**
 * A page that needs a role or scope. Without it, says so in place of the page
 * (the sidebar already hides the link; this covers a typed or shared URL).
 */
export function Guard({
	requires,
	title,
	children,
}: {
	requires: Requirement;
	title: string;
	children: React.ReactNode;
}) {
	const access = useAccess();
	if (access.allows(requires)) {
		return <>{children}</>;
	}
	return (
		<>
			<PageHeader title={title} />
			<PageBody>
				<EmptyState
					description={deniedReason(requires, access)}
					icon={<LockKeyholeIcon className="size-4" />}
					title={`You don't have access to ${title.toLowerCase()}`}
				/>
			</PageBody>
		</>
	);
}

/**
 * An action that needs a role or scope. Without it, the control stays visible
 * but disabled, and its tooltip says why — hiding it would leave people
 * wondering where it went.
 */
export function Gated({
	requires,
	children,
	hide = false,
}: {
	requires: Requirement;
	children: React.ReactElement<{ disabled?: boolean }>;
	/** Render nothing instead of a disabled control. */
	hide?: boolean;
}) {
	const access = useAccess();
	if (access.allows(requires)) {
		return children;
	}
	if (hide || !isValidElement(children)) {
		return null;
	}
	return (
		<Tooltip content={deniedReason(requires, access)}>
			{/* A disabled button gets no pointer events, so the span takes the
			    hover; the reason is also in the accessible name. */}
			<span className="inline-flex cursor-not-allowed">
				{cloneElement(children, { disabled: true })}
				<span className="sr-only">{deniedReason(requires, access)}</span>
			</span>
		</Tooltip>
	);
}
