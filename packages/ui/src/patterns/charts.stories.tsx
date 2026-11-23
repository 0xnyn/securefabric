import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Card } from "../components/card";
import {
	BarList,
	DonutChart,
	Sparkline,
	StackedAreaChart,
	StackedBarChart,
} from "./charts";

const DAYS = [
	"Nov 18",
	"Nov 19",
	"Nov 20",
	"Nov 21",
	"Nov 22",
	"Nov 23",
	"Nov 24",
];

const meta = {
	args: {
		ariaLabel: "API calls per day",
		data: DAYS.map((label, i) => ({
			api_calls: 400 + ((i * 137) % 300),
			label,
		})),
		series: [
			{ color: "var(--ds-accent)", key: "api_calls", label: "API calls" },
		],
	},
	component: StackedBarChart,
	decorators: [
		(Story) => (
			<Card className="max-w-2xl p-5">
				<Story />
			</Card>
		),
	],
	title: "Patterns/Charts",
} satisfies Meta<typeof StackedBarChart>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Bars: Story = {};

export const StackedArea: Story = {
	render: () => (
		<StackedAreaChart
			ariaLabel="Records written"
			data={DAYS.map((label, i) => ({
				findings: 200 + i * 40,
				label,
				resources: 80 + i * 12,
			}))}
			series={[
				{ color: "var(--ds-accent)", key: "findings", label: "Findings" },
				{
					color: "var(--ds-severity-medium)",
					key: "resources",
					label: "Resources",
				},
			]}
		/>
	),
};

export const Donut: Story = {
	render: () => (
		<DonutChart
			ariaLabel="Connections by health"
			slices={[
				{
					color: "var(--ds-success)",
					key: "HEALTHY",
					label: "Healthy",
					value: 9,
				},
				{
					color: "var(--ds-severity-medium)",
					key: "RATE_LIMIT",
					label: "Rate limited",
					value: 2,
				},
				{
					color: "var(--ds-warn)",
					key: "UNAUTHORIZED",
					label: "Unauthorized",
					value: 1,
				},
			]}
			total={12}
			totalLabel="connections"
		/>
	),
};

export const RankedList: Story = {
	render: () => (
		<BarList
			items={[
				{ key: "c", label: "Critical", value: 4 },
				{ key: "h", label: "High", value: 18 },
				{ key: "m", label: "Medium", value: 41 },
				{ key: "l", label: "Low", value: 77 },
			]}
		/>
	),
};

export const SparklineTrend: Story = {
	render: () => (
		<Sparkline className="h-10 w-48" values={[3, 5, 4, 8, 6, 9, 12, 10]} />
	),
};
