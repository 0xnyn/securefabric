import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Button } from "./button";
import { Tooltip } from "./tooltip";

const meta = {
	args: {
		children: <Button>Hover me</Button>,
		content:
			"Only admins can do this. Ask an admin on your team to change your Developer role.",
	},
	component: Tooltip,
	title: "Components/Tooltip",
} satisfies Meta<typeof Tooltip>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};
