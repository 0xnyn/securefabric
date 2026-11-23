import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Badge } from "./badge";
import { Card } from "./card";
import { Table, Td, Th, Tr } from "./table";

const STATES = {
	error: "Down",
	ok: "Operational",
	warn: "Degraded",
} as const;

const meta = {
	component: Table,
	title: "Components/Table",
} satisfies Meta<typeof Table>;

export default meta;
type Story = StoryObj<typeof meta>;

export const InACard: Story = {
	render: () => (
		<Card className="max-w-2xl">
			<Table>
				<thead>
					<Tr>
						<Th>Service</Th>
						<Th>Detail</Th>
						<Th className="text-right">State</Th>
					</Tr>
				</thead>
				<tbody>
					{[
						["API", "Answers in 61 ms", "ok"],
						["Sync queue", "Oldest sync waiting 3m", "warn"],
						["Data store", "Unreachable", "error"],
					].map(([name, detail, tone]) => (
						<Tr key={name}>
							<Td className="font-medium">{name}</Td>
							<Td className="text-muted-foreground">{detail}</Td>
							<Td className="text-right">
								<Badge tone={tone as "ok" | "warn" | "error"}>
									{STATES[tone as keyof typeof STATES]}
								</Badge>
							</Td>
						</Tr>
					))}
				</tbody>
			</Table>
		</Card>
	),
};
