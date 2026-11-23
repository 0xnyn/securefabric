import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { CodeBlock, CodeTabs } from "./code";

const meta = {
	args: {
		code: JSON.stringify(
			{ id: "01a20a1d", severity: "HIGH", state: "OPEN" },
			null,
			2
		),
		json: true,
		title: "Response",
	},
	component: CodeBlock,
	title: "Patterns/Code",
} satisfies Meta<typeof CodeBlock>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Json: Story = {};

export const Tabs: Story = {
	render: () => (
		<CodeTabs
			samples={[
				{
					code: 'curl https://api.securefabric.dev/v1/vulnerability_findings \\\n  -H "Authorization: Bearer $SF_KEY"',
					label: "cURL",
				},
				{
					code: 'const { data } = await sf.GET("/v1/vulnerability_findings");',
					label: "TypeScript",
				},
			]}
		/>
	),
};
