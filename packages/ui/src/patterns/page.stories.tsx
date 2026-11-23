import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Button } from "../components/button";
import { Card } from "../components/card";
import { EmptyState } from "../components/empty-state";
import { PageBody, PageHeader } from "./page";
import { Section } from "./section";
import { Stat } from "./stat";

const meta = {
	args: { title: "Metrics" },
	component: PageHeader,
	parameters: {
		docs: {
			description: {
				component:
					"The page vocabulary: a header (title, one-sentence description, actions), then stat tiles, then `Section`s that each hold a `Card`. Sections side by side end at the same height.",
			},
		},
	},
	title: "Patterns/Page",
} satisfies Meta<typeof PageHeader>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Layout: Story = {
	render: () => (
		<div className="-m-6">
			<PageHeader
				actions={<Button variant="primary">Add connection</Button>}
				description="See how your connections, findings and syncs are doing in this environment."
				title="Development"
			/>
			<PageBody className="grid gap-8">
				<div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
					<Stat hint="All healthy" label="Active connections" value="12" />
					<Stat label="Records stored" value="48.2k" />
					<Stat hint="None failed" label="Jobs, last 24 hours" value="96" />
					<Stat label="API calls, last 24 hours" value="1.2k" />
				</div>
				<div className="grid gap-6 lg:grid-cols-2">
					<Section
						description="Every connection, by health."
						title="Connections"
					>
						<Card className="p-5">
							<div className="bg-muted h-48 rounded-md" />
						</Card>
					</Section>
					<Section
						action={
							<Button size="sm" variant="ghost">
								View all logs
							</Button>
						}
						description="Connections that aren't syncing."
						title="Needs attention"
					>
						<Card>
							<EmptyState
								description="Connections that stop syncing show here."
								title="Nothing needs attention"
							/>
						</Card>
					</Section>
				</div>
			</PageBody>
		</div>
	),
};
