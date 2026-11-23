import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { CONNECTOR_LOGOS, PLANNED } from "@/lib/connector-catalog";
import { ConnectorLogo } from "./connector-logo";

const meta = {
	args: { id: "GITHUB", name: "GitHub Advanced Security", size: 40 },
	component: ConnectorLogo,
	parameters: {
		docs: {
			description: {
				component:
					"Every mark sits on a tile that is white in light mode and a faint lift in dark mode. Marks that are dark on transparent (GitHub, AWS, Snyk) ship a light twin. Toggle the theme in the toolbar to check both.",
			},
		},
	},
	title: "Domain/Connector logo",
} satisfies Meta<typeof ConnectorLogo>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};
export const Muted: Story = {
	args: { id: "TENABLE", muted: true, name: "Tenable" },
};
export const Monogram: Story = {
	args: { id: "BLACK_DUCK_SCA", name: "Black Duck SCA" },
};

/** Every logo the catalog can show, plus a monogram fallback. */
export const AllLogos: Story = {
	render: () => {
		const names = new Map(PLANNED.map((p) => [p.id, p.name]));
		const ids = [
			...new Set([...Object.keys(CONNECTOR_LOGOS), "BLACK_DUCK_SCA"]),
		].sort();
		return (
			<div className="grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-4">
				{ids.map((id) => (
					<div className="flex items-center gap-2" key={id}>
						<ConnectorLogo id={id} name={names.get(id) ?? id} size={32} />
						<span className="text-muted-foreground truncate text-xs">
							{names.get(id) ?? id}
						</span>
					</div>
				))}
			</div>
		);
	},
};
