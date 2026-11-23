import { TooltipProvider } from "@securefabric/ui/components/tooltip";
import { withThemeByClassName } from "@storybook/addon-themes";
import type { Preview } from "@storybook/nextjs-vite";
import "./preview.css";

const preview: Preview = {
	decorators: [
		(Story) => (
			<TooltipProvider>
				<div className="bg-background text-foreground p-6 font-sans antialiased">
					<Story />
				</div>
			</TooltipProvider>
		),
		// The app themes with next-themes' class strategy: `.dark` on <html>.
		withThemeByClassName({
			defaultTheme: "light",
			parentSelector: "html",
			themes: { dark: "dark", light: "" },
		}),
	],
	parameters: {
		a11y: { test: "error" },
		backgrounds: { disable: true },
		controls: { expanded: true, sort: "requiredFirst" },
		layout: "fullscreen",
		nextjs: { appDirectory: true },
		options: {
			storySort: {
				order: [
					"Introduction",
					"Components",
					"Patterns",
					"Domain",
					"Primitives",
				],
			},
		},
	},
	tags: ["autodocs"],
};

export default preview;
