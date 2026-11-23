import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { HEALTH, JOB_TONES, SEVERITIES } from "@/lib/types";
import { HealthBadge, SeverityLabel, StatusBadge } from "./badges";

const meta = {
	args: { health: "HEALTHY" },
	argTypes: { health: { control: "select", options: Object.keys(HEALTH) } },
	component: HealthBadge,
	title: "Domain/Badges",
} satisfies Meta<typeof HealthBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Health: Story = {};

export const EveryHealthCode: Story = {
	render: () => (
		<div className="flex flex-wrap gap-2">
			{Object.keys(HEALTH).map((code) => (
				<HealthBadge health={code} key={code} />
			))}
		</div>
	),
};

export const JobStatus: Story = {
	render: () => (
		<div className="flex flex-wrap gap-2">
			{Object.keys(JOB_TONES).map((s) => (
				<StatusBadge key={s} tones={JOB_TONES} value={s} />
			))}
		</div>
	),
};

export const Severity: Story = {
	render: () => (
		<div className="grid gap-2">
			{SEVERITIES.map((s) => (
				<SeverityLabel key={s} value={s} />
			))}
		</div>
	),
};
