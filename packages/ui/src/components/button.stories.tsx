import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { PlusIcon, Trash2Icon } from "lucide-react";
import { Button } from "./button";
import { Input } from "./form";

const meta = {
	args: { children: "Add connection" },
	argTypes: {
		size: {
			control: "inline-radio",
			options: ["xs", "sm", "md", "lg", "icon-sm", "icon", "icon-lg"],
		},
		variant: {
			control: "inline-radio",
			options: [
				"primary",
				"secondary",
				"outline",
				"ghost",
				"destructive",
				"link",
			],
		},
	},
	component: Button,
	parameters: {
		docs: {
			description: {
				component:
					"Verb + object labels (“Add connection”, “Revoke key”). One `primary` per page. Sizes share one height scale with inputs and selects: xs 28, sm 32, md 36, lg 40.",
			},
		},
	},
	title: "Components/Button",
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = { args: { variant: "primary" } };
export const Secondary: Story = {};
export const Destructive: Story = {
	args: { children: "Revoke key", variant: "destructive" },
};

export const Variants: Story = {
	render: () => (
		<div className="flex flex-wrap items-center gap-2">
			<Button variant="primary">Primary</Button>
			<Button>Secondary</Button>
			<Button variant="outline">Outline</Button>
			<Button variant="ghost">Ghost</Button>
			<Button variant="destructive">Destructive</Button>
			<Button variant="link">Link</Button>
			<Button disabled variant="primary">
				Disabled
			</Button>
		</div>
	),
};

/** Every size lines up with an input of the same size. */
export const SizesAlignWithInputs: Story = {
	render: () => (
		<div className="grid gap-3">
			<div className="flex items-center gap-2">
				<Input className="h-8 w-56" placeholder="Search (sm)" />
				<Button size="sm">Filter</Button>
				<Button size="sm" variant="primary">
					<PlusIcon /> Add
				</Button>
			</div>
			<div className="flex items-center gap-2">
				<Input className="w-56" placeholder="Search (md)" />
				<Button>Filter</Button>
				<Button variant="primary">
					<PlusIcon /> Add
				</Button>
				<Button aria-label="Delete" size="icon" variant="ghost">
					<Trash2Icon />
				</Button>
			</div>
		</div>
	),
};
