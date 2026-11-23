import { defineConfig } from "vitest/config";

// Runs the tests that came with the vendored data-table blocks, so a re-add
// or a local edit (marked `securefabric:`) is checked against upstream behaviour.
export default defineConfig({
	resolve: { tsconfigPaths: true },
	test: {
		environment: "node",
		exclude: ["node_modules/**", ".next/**"],
	},
});
