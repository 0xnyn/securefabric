import { Card } from "@securefabric/ui/components/card";
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { QueryState } from "./query-state";

const ok = {
	error: null,
	isError: false,
	isPending: false,
	refetch: () => undefined,
};

const meta = {
	args: { children: <p className="text-sm">The data.</p>, query: ok },
	component: QueryState,
	decorators: [
		(Story) => (
			<Card className="max-w-xl p-5">
				<Story />
			</Card>
		),
	],
	parameters: {
		docs: {
			description: {
				component:
					"Loading, error and empty in one place. Errors say what failed and offer “Try again”; empty states say what will appear and the next step.",
			},
		},
	},
	title: "Domain/Query state",
} satisfies Meta<typeof QueryState>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Loaded: Story = {};
export const Loading: Story = { args: { query: { ...ok, isPending: true } } };
export const Failed: Story = {
	args: {
		query: {
			...ok,
			error: new Error("The API answered 502 (req_8cd76e31)."),
			isError: true,
		},
	},
};
export const Empty: Story = {
	args: {
		empty: {
			description: "Syncs show here as soon as one starts.",
			title: "No syncs yet",
			when: true,
		},
	},
};
