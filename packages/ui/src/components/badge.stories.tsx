import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Badge, Dot, type Tone } from "./badge";

const TONES: Tone[] = ["neutral", "ok", "warn", "error", "busy", "accent"];

const meta = {
	args: { children: "Active", tone: "ok" },
	argTypes: { tone: { control: "inline-radio", options: TONES } },
	component: Badge,
	title: "Components/Badge",
} satisfies Meta<typeof Badge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

/** Badges say a state in a word, sentence case, never a raw enum. */
export const Tones: Story = {
	render: () => (
		<div className="flex flex-wrap gap-2">
			{TONES.map((tone) => (
				<Badge key={tone} tone={tone}>
					<Dot className="size-1.5" tone={tone} />
					{tone.charAt(0).toUpperCase() + tone.slice(1)}
				</Badge>
			))}
		</div>
	),
};
