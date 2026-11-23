import { fileURLToPath } from "node:url";
import type { StorybookConfig } from "@storybook/nextjs-vite";
import tailwindcss from "@tailwindcss/vite";

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url));

/**
 * One Storybook for the whole UI:
 * - packages/ui: the design system (components, patterns, vendored primitives)
 * - apps/dash/src/components/domain: SecureFabric-aware building blocks
 *
 * Stories sit next to the component they show (`button.stories.tsx` beside
 * `button.tsx`). The Next.js framework mocks next/image, next/link and
 * next/navigation, which the domain components use.
 */
const config: StorybookConfig = {
	addons: [
		"@storybook/addon-docs",
		"@storybook/addon-a11y",
		"@storybook/addon-themes",
	],
	core: { disableTelemetry: true },
	framework: { name: "@storybook/nextjs-vite", options: {} },
	staticDirs: [{ from: "../../dash/public", to: "/" }],
	stories: [
		"../src/**/*.mdx",
		"../../../packages/ui/src/**/*.stories.tsx",
		"../../dash/src/components/domain/**/*.stories.tsx",
	],
	viteFinal(vite) {
		vite.plugins = [...(vite.plugins ?? []), tailwindcss()];
		vite.resolve = {
			...vite.resolve,
			alias: {
				...(vite.resolve?.alias as Record<string, string> | undefined),
				"@": here("../../dash/src"),
			},
			dedupe: ["react", "react-dom", "@tanstack/react-query"],
		};
		return vite;
	},
};

export default config;
