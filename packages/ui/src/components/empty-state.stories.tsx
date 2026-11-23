import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { CircleCheckIcon, InboxIcon } from "lucide-react";
import { Button } from "./button";
import { Card } from "./card";
import { EmptyState } from "./empty-state";

const meta = {
	args: {
		action: (
			<Button size="sm" variant="primary">
				Add connection
			</Button>
		),
		description:
			"Connect a customer's security tool to start syncing their findings and resources.",
		icon: <InboxIcon className="size-4" />,
		title: "No connections yet",
	},
	component: EmptyState,
	parameters: {
		docs: {
			description: {
				component:
					"Say what will appear here and offer the next step. On a page it has a dashed frame; inside a `Card` it drops the frame and fills the card, so cards side by side keep the same height.",
			},
		},
	},
	title: "Components/Empty state",
} satisfies Meta<typeof EmptyState>;

export default meta;
type Story = StoryObj<typeof meta>;

export const OnAPage: Story = {};

export const InsideCardsSideBySide: Story = {
	render: () => (
		<div className="grid gap-6 md:grid-cols-2">
			<Card className="p-5">
				<EmptyState
					description="Connection health shows here once a customer connects a tool."
					icon={<InboxIcon className="size-4" />}
					title="No connections yet"
				/>
			</Card>
			<Card className="p-5">
				<EmptyState
					description="Connections that stop syncing show here, with who has to fix them."
					icon={<CircleCheckIcon className="size-4" />}
					title="Nothing needs attention"
				/>
			</Card>
		</div>
	),
};
