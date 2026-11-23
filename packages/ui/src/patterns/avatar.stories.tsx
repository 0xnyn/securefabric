import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { EntityAvatar, PersonAvatar } from "./avatar";

const meta = {
	args: { seed: "ada@example.com", size: 36 },
	component: PersonAvatar,
	parameters: {
		docs: {
			description: {
				component:
					"Only people get generated art: a round `beam`, the same for the same email every time. Organizations and accounts get their initial on a plain square, so a customer never reads as a teammate.",
			},
		},
	},
	title: "Patterns/Avatar",
} satisfies Meta<typeof PersonAvatar>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Person: Story = {};

export const Entity: StoryObj<typeof EntityAvatar> = {
	args: { name: "Acme Corp", size: 36 },
	render: (args) => <EntityAvatar {...args} />,
};

export const PeopleAndEntities: Story = {
	render: () => (
		<div className="grid gap-4">
			<div className="flex gap-3">
				{[
					"ada@example.com",
					"grace@example.com",
					"linus@example.com",
					"radia@example.com",
				].map((s) => (
					<PersonAvatar key={s} seed={s} size={36} />
				))}
			</div>
			<div className="flex gap-3">
				{["Acme Corp", "Globex", "Initech", "Umbrella"].map((s) => (
					<EntityAvatar key={s} name={s} size={36} />
				))}
			</div>
		</div>
	),
};
