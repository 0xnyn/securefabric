import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Button } from "./button";
import { Card, CardFooter, CardHeader } from "./card";
import { Input } from "./form";

const meta = {
	component: Card,
	title: "Components/Card",
} satisfies Meta<typeof Card>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Settings: Story = {
	render: () => (
		<Card className="max-w-xl">
			<CardHeader
				description="Shown in the environment switcher and on emails to your team."
				title="Environment name"
			/>
			<div className="p-5">
				<Input aria-label="Environment name" defaultValue="Development" />
			</div>
			<CardFooter>
				<span>Up to 80 characters.</span>
				<Button size="sm" variant="primary">
					Save
				</Button>
			</CardFooter>
		</Card>
	),
};
