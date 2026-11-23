import type { Me } from "@/lib/types";

/**
 * Who may see and do what. The API is the authority — every rule here mirrors
 * a check in `packages/domain` (`principal.require(scope)` or
 * `require_admin()`) — so the dashboard never offers something the API would
 * refuse with a 403.
 *
 * Signed-in people get their role's scopes (tenancy.ROLE_SCOPES). An API key
 * (local development) has whatever scopes it was created with and counts as an
 * admin, because `require_admin` only checks people.
 */

export type Role = "admin" | "developer" | "support";

export type Scope =
	| "provisioning:read"
	| "provisioning:write"
	| "data:read"
	| "jobs:execute"
	| "webhooks:manage"
	| "keys:manage"
	| "actions:write";

/** A requirement on a page or an action. Both parts must hold. */
export interface Requirement {
	/** Needs the admin role (team, audit log, environment settings). */
	admin?: boolean;
	scope?: Scope;
}

export interface RoleInfo {
	/** One line on what the role is for. */
	description: string;
	label: string;
	value: Role;
}

export const ROLES: RoleInfo[] = [
	{
		description:
			"Full access, including API keys, the team, settings and the audit log.",
		label: "Admin",
		value: "admin",
	},
	{
		description:
			"Builds the integration: connections, syncs, webhooks and the API. Can't manage keys, the team or settings.",
		label: "Developer",
		value: "developer",
	},
	{
		description: "Read-only access to connections, findings, logs and status.",
		label: "Support",
		value: "support",
	},
];

export function roleInfo(role: string | null | undefined): RoleInfo | null {
	return ROLES.find((r) => r.value === role) ?? null;
}

export interface Access {
	/** Whether the requirement holds. No requirement always holds. */
	allows: (requirement?: Requirement) => boolean;
	can: (scope: Scope) => boolean;
	isAdmin: boolean;
	/** True when nothing can be changed (the support role, or a read-only key). */
	readOnly: boolean;
	role: RoleInfo | null;
}

export function accessFor(me: Pick<Me, "kind" | "role" | "scopes">): Access {
	const scopes = new Set(me.scopes);
	const isAdmin = me.kind !== "user" || me.role === "admin";
	const can = (scope: Scope) => scopes.has(scope);
	return {
		allows: (r) =>
			r === undefined ||
			((!r.admin || isAdmin) && (r.scope === undefined || can(r.scope))),
		can,
		isAdmin,
		readOnly: !(
			can("provisioning:write") ||
			can("jobs:execute") ||
			can("webhooks:manage")
		),
		role: roleInfo(me.role),
	};
}

/** The sentence shown on a disabled control or a locked page. */
export function deniedReason(
	requirement: Requirement | undefined,
	access: Access
): string {
	const who = access.role ? `your ${access.role.label} role` : "this API key";
	if (requirement?.admin && !access.isAdmin) {
		return `Only admins can do this. Ask an admin on your team to change ${who}.`;
	}
	return `${capitalize(who)} doesn't include this. Ask an admin for access.`;
}

function capitalize(s: string): string {
	return s.charAt(0).toUpperCase() + s.slice(1);
}
