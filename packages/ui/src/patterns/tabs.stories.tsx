import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { useState } from "react";
import { Tabs } from "./tabs";

const meta = {
	args: {
		onChange: () => undefined,
		tabs: [
			{ label: "Overview", value: "overview" },
			{ count: 3, label: "Streams", value: "streams" },
			{ label: "Logs", value: "logs" },
		],
		value: "overview",
	},
	component: Tabs,
	title: "Patterns/Tabs",
} satisfies Meta<typeof Tabs>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	render: (args) => {
		const [value, setValue] = useState(args.value);
		return <Tabs {...args} onChange={setValue} value={value} />;
	},
};
