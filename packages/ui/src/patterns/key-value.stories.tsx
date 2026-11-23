import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { KeyValue } from "./key-value";

const meta = {
	args: {
		items: [
			{ label: "Connection ID", value: "01a20a1d-5d54-739e" },
			{ label: "Organization", value: "Acme Corp" },
			{ label: "Last sync", value: "3 minutes ago" },
			{ label: "Next sync", value: "in 57 minutes" },
		],
	},
	component: KeyValue,
	title: "Patterns/Key-value",
} satisfies Meta<typeof KeyValue>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};
