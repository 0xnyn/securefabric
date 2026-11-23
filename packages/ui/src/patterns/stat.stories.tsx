import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Stat } from "./stat";

const meta = {
	args: { hint: "of 3", label: "Sync workers online", value: "1" },
	component: Stat,
	title: "Patterns/Stat",
} satisfies Meta<typeof Stat>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};
export const WithoutHint: Story = {
	args: { hint: undefined, label: "Records stored", value: "48.2k" },
};
