import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { CopyButton, CopyField, SecretRow } from "./copy";

const meta = {
	args: {
		label: "Environment ID",
		value: "01a20a18-1878-7746-8c5d-15f0cd12e49f",
	},
	component: CopyButton,
	title: "Patterns/Copy",
} satisfies Meta<typeof CopyButton>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Button: Story = {};

export const Field: Story = {
	render: () => (
		<div className="max-w-md">
			<CopyField
				label="Connect link"
				value="https://connect.securefabric.dev/c/abc123"
			/>
		</div>
	),
};

export const Secret: Story = {
	render: () => (
		<div className="max-w-md">
			<SecretRow
				help="Shown once. Store it in your secret manager now."
				label="API key"
				value="sfk_test_us_TNp2Eaz0yy9iFbxskblf2kd2DhlBWnWODOOSLA8maZL"
			/>
		</div>
	),
};
