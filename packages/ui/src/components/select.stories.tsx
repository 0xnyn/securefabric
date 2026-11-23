import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { useState } from "react";
import { Select } from "./select";

const OPTIONS = [
	{ description: "Full access", label: "Admin", value: "admin" },
	{
		description: "Everything but keys and team",
		label: "Developer",
		value: "developer",
	},
	{ description: "Read-only", label: "Support", value: "support" },
];

const meta = {
	args: {
		ariaLabel: "Role",
		onChange: () => undefined,
		options: OPTIONS,
		value: "developer",
	},
	component: Select,
	title: "Components/Select",
} satisfies Meta<typeof Select>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	render: (args) => {
		const [value, setValue] = useState(args.value);
		return (
			<div className="w-56">
				<Select {...args} onChange={setValue} value={value} />
			</div>
		);
	},
};

export const Small: Story = { ...Default, args: { size: "sm" } };
export const Disabled: Story = { ...Default, args: { disabled: true } };
