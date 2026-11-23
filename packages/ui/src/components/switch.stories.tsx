import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { useState } from "react";
import { Switch } from "./switch";

const meta = {
	args: { ariaLabel: "Enabled", checked: true, onChange: () => undefined },
	component: Switch,
	title: "Components/Switch",
} satisfies Meta<typeof Switch>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
	render: (args) => {
		const [on, setOn] = useState(args.checked);
		return <Switch {...args} checked={on} onChange={setOn} />;
	},
};
export const Disabled: Story = { args: { disabled: true } };
