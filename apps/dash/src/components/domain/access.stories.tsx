import { Button } from "@securefabric/ui/components/button";
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import type * as React from "react";
import { EnvContext } from "@/components/shell/env-context";
import type { ApiClient } from "@/lib/api";
import type { Environment, Me } from "@/lib/types";
import { Gated, Guard } from "./access";

// The scopes each role gets (tenancy.ROLE_SCOPES in packages/domain).
const SCOPES: Record<string, string[]> = {
	admin: [
		"actions:write",
		"data:read",
		"jobs:execute",
		"keys:manage",
		"provisioning:read",
		"provisioning:write",
		"webhooks:manage",
	],
	developer: [
		"actions:write",
		"data:read",
		"jobs:execute",
		"provisioning:read",
		"provisioning:write",
		"webhooks:manage",
	],
	support: ["data:read", "provisioning:read"],
};

const env = {
	id: "env",
	is_production: false,
	name: "Development",
	settings: {},
	slug: "dev",
} as Environment;

/** Renders its children as a signed-in person with the given role. */
function AsPersona({
	persona,
	children,
}: {
	persona: string;
	children: React.ReactNode;
}) {
	const me = {
		actor_id: "u1",
		kind: "user",
		role: persona,
		scopes: SCOPES[persona] ?? [],
	} as unknown as Me;
	return (
		<EnvContext
			value={{
				client: {} as ApiClient,
				devMode: false,
				env,
				environments: [env],
				me,
			}}
		>
			{children}
		</EnvContext>
	);
}

/** `Gated` as a person with that role sees it. */
function GatedAs({
	persona,
	...props
}: React.ComponentProps<typeof Gated> & { persona: string }) {
	return (
		<AsPersona persona={persona}>
			<Gated {...props} />
		</AsPersona>
	);
}

const meta = {
	args: {
		children: <Button variant="primary">Create key</Button>,
		persona: "developer",
		requires: { scope: "keys:manage" },
	},
	argTypes: {
		persona: {
			control: "inline-radio",
			options: ["admin", "developer", "support"],
		},
	},
	component: GatedAs,
	parameters: {
		docs: {
			description: {
				component:
					"Write controls stay visible but disabled when the role can't use them, with a tooltip saying why. `Guard` does the same for a whole page.",
			},
		},
	},
	title: "Domain/Access",
} satisfies Meta<typeof GatedAs>;

export default meta;
type Story = StoryObj<typeof meta>;

export const DeveloperCantManageKeys: Story = {};
export const AdminCan: Story = { args: { persona: "admin" } };

export const SupportSeesLockedPage: Story = {
	render: () => (
		<AsPersona persona="support">
			<Guard requires={{ scope: "webhooks:manage" }} title="Webhooks">
				<p>Hidden.</p>
			</Guard>
		</AsPersona>
	),
};
