import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Button } from "./button";
import {
	Menu,
	MenuContent,
	MenuItem,
	MenuLabel,
	MenuSeparator,
	MenuTrigger,
} from "./menu";

const meta = {
	component: Menu,
	title: "Components/Menu",
} satisfies Meta<typeof Menu>;

export default meta;
type Story = StoryObj<typeof meta>;

export const RowActions: Story = {
	render: () => (
		<Menu>
			<MenuTrigger render={<Button size="sm" />}>Actions</MenuTrigger>
			<MenuContent>
				<MenuLabel>Connection</MenuLabel>
				<MenuItem>Sync now</MenuItem>
				<MenuItem>Pause syncing</MenuItem>
				<MenuSeparator />
				<MenuItem>Delete connection</MenuItem>
			</MenuContent>
		</Menu>
	),
};
