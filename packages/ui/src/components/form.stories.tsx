import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Field, Input, Textarea } from "./form";

const meta = {
	args: { children: null, label: "Endpoint URL" },
	component: Field,
	title: "Components/Form",
} satisfies Meta<typeof Field>;

export default meta;
type Story = StoryObj<typeof meta>;

/** Labels are nouns; help is one short sentence; placeholders show an example. */
export const Fields: Story = {
	render: () => (
		<div className="grid max-w-md gap-5">
			<Field
				help="We send a POST for every event you pick."
				htmlFor="url"
				label="Endpoint URL"
			>
				<Input id="url" placeholder="https://api.example.com/webhooks" />
			</Field>
			<Field help="Use an https:// address." htmlFor="bad" label="Logo URL">
				<Input
					aria-invalid
					defaultValue="http://example.com/logo.png"
					id="bad"
				/>
			</Field>
			<Field htmlFor="origins" label="Redirect origins">
				<Textarea id="origins" placeholder="https://app.example.com" rows={3} />
			</Field>
			<Field htmlFor="off" label="Disabled">
				<Input disabled id="off" value="Read-only for your role" />
			</Field>
		</div>
	),
};
