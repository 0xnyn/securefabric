#!/usr/bin/env node
/**
 * Exports the provider catalog (src/lib/catalog.ts, the source of truth for
 * every provider the dash shows) to the JSON the backend validates against:
 * packages/domain/src/securefabric_domain/catalog.json.
 *
 *   node scripts/export-catalog.mjs          # write it
 *   node scripts/export-catalog.mjs --check  # fail if it is stale (CI, hooks)
 *
 * Only what the API needs crosses over: slugs, names, status, models,
 * credential fields (to mask secrets) and write actions. Node runs the .ts
 * file directly (type stripping), so there is no build step.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const target = resolve(
	here,
	"../../../packages/domain/src/securefabric_domain/catalog.json"
);
const { MODELS, PROVIDERS } = await import("../src/lib/catalog.ts");

const catalog = {
	$comment:
		"Generated from apps/dash/src/lib/catalog.ts by `pnpm -F dash export-catalog`. Do not edit.",
	models: Object.keys(MODELS).sort(),
	providers: PROVIDERS.map((p) => ({
		fields: p.fields.map((f) => ({
			key: f.key,
			options: f.options?.map((o) => o.value) ?? null,
			secret: Boolean(f.secret),
		})),
		models: p.models,
		name: p.name,
		slug: p.slug,
		status: p.status,
		writeActions: p.writeActions.map((a) => ({
			endpoint: a.endpoint,
			name: a.name,
			scope: a.scope,
		})),
	})).sort((a, b) => a.slug.localeCompare(b.slug)),
};

const json = `${JSON.stringify(catalog, null, 2)}\n`;

if (process.argv.includes("--check")) {
	let current = "";
	try {
		current = readFileSync(target, "utf8");
	} catch {
		// Missing counts as stale.
	}
	if (current !== json) {
		console.error(
			"catalog.json is out of date with apps/dash/src/lib/catalog.ts. Run: make generate"
		);
		process.exit(1);
	}
	console.log("catalog.json is up to date");
} else {
	writeFileSync(target, json);
	console.log(`wrote ${target} (${catalog.providers.length} providers)`);
}
