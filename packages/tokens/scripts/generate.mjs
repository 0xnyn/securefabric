#!/usr/bin/env node
/**
 * Generates the two files derived from `src/tokens.ts`:
 *
 * - `src/theme.css`: CSS custom properties for both themes, the shadcn role
 *   variables mapped onto them, and the Tailwind v4 `@theme` block.
 * - The YAML front matter of `DESIGN.md` (Google's DESIGN.md format). The
 *   prose below the front matter is hand-written and left untouched.
 *
 * Writing either by hand guarantees drift: `bg-ds-primary`, `color.light.primary`
 * and DESIGN.md's `primary` would quietly stop being the same colour. So both
 * are generated, and `--check` fails CI when either is stale.
 *
 * Node strips the types from tokens.ts on import, so there is no build step.
 *
 * Usage:
 *   node scripts/generate.mjs           # write both files
 *   node scripts/generate.mjs --check   # exit 1 if either is stale
 */

import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
	color,
	font,
	layout,
	motion,
	radius,
	shadow,
	space,
	text,
} from "../src/tokens.ts";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const THEME_CSS = path.resolve(HERE, "../src/theme.css");
const DESIGN_MD = path.resolve(HERE, "../DESIGN.md");

const CAMEL_BOUNDARY = /(?<before>[a-z0-9])(?<after>[A-Z])/gu;
const PLAIN_YAML = /^[\w.-]+$/u;
const FRONT_MATTER = /^---\n[\s\S]*?\n---\n/u;

/** `lineAccent` → `line-accent`. */
const kebab = (key) => key.replace(CAMEL_BOUNDARY, "$1-$2").toLowerCase();

/** Pixel value of a px or rem size, for ordering the type scale. */
const toPx = (size) =>
	size.endsWith("rem") ? Number.parseFloat(size) * 16 : Number.parseFloat(size);

/** The type scale, smallest first, whatever order the source keeps it in. */
const textSteps = Object.entries(text).sort(
	([, a], [, b]) => toPx(a.fontSize) - toPx(b.fontSize)
);

/** Colour roles in a stable, readable order: the light theme's key order. */
const roles = Object.keys(color.light);

/**
 * shadcn's role variables, as `packages/ui` components expect them, each
 * pointed at an SecureFabric role. Because they reference `--ds-*`, they follow the
 * theme automatically.
 */
const SHADCN = {
	accent: "surface",
	"accent-foreground": "fg",
	background: "bg",
	border: "line",
	card: "card",
	"card-foreground": "fg",
	"chart-1": "primary",
	"chart-2": "primary-mid",
	"chart-3": "accent",
	"chart-4": "muted",
	"chart-5": "success",
	destructive: "warn-text",
	foreground: "fg",
	input: "line",
	muted: "surface",
	"muted-foreground": "muted",
	popover: "card",
	"popover-foreground": "fg",
	primary: "primary",
	"primary-foreground": "primary-fg",
	ring: "primary",
	secondary: "surface",
	"secondary-foreground": "fg",
	sidebar: "shell",
	"sidebar-accent": "surface",
	"sidebar-accent-foreground": "fg",
	"sidebar-border": "line",
	"sidebar-foreground": "fg",
	"sidebar-primary": "primary",
	"sidebar-primary-foreground": "primary-fg",
	"sidebar-ring": "primary",
};

// ---------------------------------------------------------------------------
// theme.css
// ---------------------------------------------------------------------------

function block(selector, groups) {
	const body = groups
		.map(
			({ title, entries }) =>
				`\t/* ${title} */\n${entries.map(([name, value]) => `\t${name}: ${value};`).join("\n")}`
		)
		.join("\n\n");
	return `${selector} {\n${body}\n}`;
}

function themeCss() {
	const colorEntries = (mode) =>
		roles.map((role) => [`--ds-${kebab(role)}`, color[mode][role]]);

	const root = block(":root", [
		{
			entries: colorEntries("light"),
			title: "Colour roles, light (the brand)",
		},
		{
			entries: [["color-scheme", "light"]],
			title: "Native controls and scrollbars follow the theme",
		},
		{
			entries: [
				["--ds-ease", motion.ease],
				...Object.entries(motion.duration).map(([key, value]) => [
					`--ds-duration-${key}`,
					value,
				]),
			],
			title: "Motion: Tailwind has no duration namespace, so these stay plain",
		},
		{
			entries: [["--radius", radius.lg]],
			title: "shadcn's base radius, for components that compute from it",
		},
	]);

	const dark = block(".dark", [
		{ entries: colorEntries("dark"), title: "Colour roles, dark" },
		{
			entries: [["color-scheme", "dark"]],
			title: "Native controls and scrollbars follow the theme",
		},
	]);

	const shadcn = block(":root,\n.dark", [
		{
			entries: Object.entries(SHADCN).map(([name, role]) => [
				`--${name}`,
				`var(--ds-${role})`,
			]),
			title: "shadcn roles, mapped onto SecureFabric roles",
		},
	]);

	const tailwind = block("@theme inline", [
		{
			entries: [
				["--font-sans", font.family.sans],
				["--font-mono", font.family.mono],
			],
			title: "Families",
		},
		{
			entries: textSteps.flatMap(([key, step]) => {
				const entries = [
					[`--text-${key}`, step.fontSize],
					[`--text-${key}--line-height`, step.lineHeight],
				];
				if ("letterSpacing" in step) {
					entries.push([`--text-${key}--letter-spacing`, step.letterSpacing]);
				}
				if ("fontWeight" in step) {
					entries.push([`--text-${key}--font-weight`, step.fontWeight]);
				}
				return entries;
			}),
			title: "Type scale",
		},
		{
			entries: Object.entries(font.weight).map(([key, value]) => [
				`--font-weight-${key}`,
				value,
			]),
			title: "Weights",
		},
		{
			entries: Object.entries(font.tracking).map(([key, value]) => [
				`--tracking-${key}`,
				value,
			]),
			title: "Tracking",
		},
		{
			entries: roles.map((role) => [
				`--color-ds-${kebab(role)}`,
				`var(--ds-${kebab(role)})`,
			]),
			title: "SecureFabric colours: bg-ds-*, text-ds-*, border-ds-*",
		},
		{
			entries: Object.keys(SHADCN).map((name) => [
				`--color-${name}`,
				`var(--${name})`,
			]),
			title: "shadcn colours: bg-primary, text-muted-foreground, ...",
		},
		{
			entries: Object.entries(radius).map(([key, value]) => [
				`--radius-${key}`,
				value,
			]),
			title: "Radii",
		},
		{
			entries: Object.entries(layout).map(([key, value]) => [
				`--container-${key}`,
				value,
			]),
			title: "Content widths: max-w-page, max-w-prose",
		},
		{ entries: [["--ease-out-quint", motion.ease]], title: "Easing" },
		{
			entries: Object.entries(shadow).map(([key, value]) => [
				`--shadow-${key}`,
				value,
			]),
			title: "Elevation",
		},
	]);

	return `/*
 * GENERATED by scripts/generate.mjs from src/tokens.ts. Do not edit.
 * Regenerate with \`pnpm -F @securefabric/tokens generate\`.
 *
 * Import once per app, after \`@import "tailwindcss"\`. The dark values apply
 * under a \`.dark\` ancestor (next-themes' class strategy).
 */

${root}

${dark}

${shadcn}

${tailwind}
`;
}

// ---------------------------------------------------------------------------
// DESIGN.md front matter
// ---------------------------------------------------------------------------

/** YAML scalar: quote anything that is not a plain word or number. */
const yaml = (value) =>
	typeof value === "number" ||
	(PLAIN_YAML.test(value) && !value.startsWith("#"))
		? String(value)
		: JSON.stringify(value);

/**
 * Components, in DESIGN.md's component-token format. Each references the
 * colour, type and radius tokens above; `lint` checks every background/text
 * pair here for WCAG AA, so the pairs the app actually draws belong here.
 * `-dark` entries are the same component in the dark theme.
 */
function components() {
	const c = (role, theme) =>
		`{colors.${theme === "dark" ? "dark-" : ""}${kebab(role)}}`;
	const both = (name, build) => [
		[name, build("light")],
		[`${name}-dark`, build("dark")],
	];
	return Object.fromEntries([
		...both("button-primary", (t) => ({
			backgroundColor: c("primary", t),
			height: "36px",
			padding: "0 16px",
			rounded: "{rounded.full}",
			textColor: c("primaryFg", t),
			typography: "{typography.sm}",
		})),
		...both("button-primary-hover", (t) => ({
			backgroundColor: c("primaryMid", t),
			textColor: c("primaryFg", t),
		})),
		...both("button-secondary", (t) => ({
			backgroundColor: c("surface", t),
			height: "36px",
			padding: "0 16px",
			rounded: "{rounded.full}",
			textColor: c("fg", t),
			typography: "{typography.sm}",
		})),
		...both("page", (t) => ({
			backgroundColor: c("bg", t),
			textColor: c("fg", t),
			typography: "{typography.base}",
		})),
		...both("page-secondary-text", (t) => ({
			backgroundColor: c("bg", t),
			textColor: c("muted", t),
		})),
		...both("link", (t) => ({
			backgroundColor: c("bg", t),
			textColor: c("accent", t),
		})),
		...both("card-shell", (t) => ({
			backgroundColor: c("shell", t),
			padding: "{spacing.sm}",
			rounded: "{rounded.3xl}",
			textColor: c("fg", t),
		})),
		...both("card", (t) => ({
			backgroundColor: c("card", t),
			padding: "{spacing.lg}",
			rounded: "{rounded.2xl}",
			textColor: c("fg", t),
		})),
		...both("input", (t) => ({
			backgroundColor: c("bg", t),
			height: "36px",
			rounded: "{rounded.lg}",
			textColor: c("fg", t),
			typography: "{typography.sm}",
		})),
		...both("error-text", (t) => ({
			backgroundColor: c("bg", t),
			textColor: c("warnText", t),
		})),
		...both("success-text", (t) => ({
			backgroundColor: c("bg", t),
			textColor: c("successText", t),
		})),
		...both("status-dot-success", (t) => ({
			backgroundColor: c("success", t),
			rounded: "{rounded.full}",
			size: "8px",
		})),
		...both("status-dot-warn", (t) => ({
			backgroundColor: c("warn", t),
			rounded: "{rounded.full}",
			size: "8px",
		})),
		...both("status-dot-high", (t) => ({
			backgroundColor: c("severityHigh", t),
			rounded: "{rounded.full}",
			size: "8px",
		})),
		...both("status-dot-medium", (t) => ({
			backgroundColor: c("severityMedium", t),
			rounded: "{rounded.full}",
			size: "8px",
		})),
		...both("divider", (t) => ({
			backgroundColor: c("line", t),
			height: "1px",
		})),
		...both("divider-accent", (t) => ({
			backgroundColor: c("lineAccent", t),
			height: "1px",
		})),
		...both("selected-outline", (t) => ({
			backgroundColor: c("primaryLight", t),
			height: "1px",
		})),
		...both("code-block", (t) => ({
			backgroundColor: c("code", t),
			padding: "{spacing.md}",
			rounded: "{rounded.xl}",
			textColor: c("codeFg", t),
			typography: "{typography.code}",
		})),
		...both("code-comment", (t) => ({
			backgroundColor: c("code", t),
			textColor: c("codeMuted", t),
		})),
	]);
}

function frontMatter() {
	const out = [
		"---",
		"# GENERATED from src/tokens.ts by scripts/generate.mjs. Do not edit this",
		"# block; edit tokens.ts and run `pnpm -F @securefabric/tokens generate`.",
		"version: alpha",
		"name: SecureFabric",
		`description: ${yaml("SecureFabric's design tokens: navy ink on white, one indigo primary, Inter for prose and UI, a mono for code.")}`,
		"colors:",
	];
	for (const role of roles) {
		out.push(`  ${kebab(role)}: ${yaml(color.light[role])}`);
	}
	for (const role of roles) {
		out.push(`  dark-${kebab(role)}: ${yaml(color.dark[role])}`);
	}

	out.push("typography:");
	for (const [key, step] of textSteps) {
		const family = "family" in step ? font.name[step.family] : font.name.sans;
		out.push(`  ${key}:`);
		out.push(`    fontFamily: ${yaml(family)}`);
		out.push(`    fontSize: ${step.fontSize}`);
		out.push(
			`    fontWeight: ${"fontWeight" in step ? step.fontWeight : font.weight.regular}`
		);
		out.push(`    lineHeight: ${step.lineHeight}`);
		if ("letterSpacing" in step) {
			out.push(`    letterSpacing: ${step.letterSpacing}`);
		}
	}

	out.push("rounded:");
	for (const [key, value] of Object.entries(radius)) {
		out.push(`  ${yaml(key)}: ${value}`);
	}

	out.push("spacing:");
	for (const [key, value] of Object.entries(space)) {
		out.push(`  ${yaml(key)}: ${value}`);
	}

	out.push("components:");
	for (const [name, props] of Object.entries(components())) {
		out.push(`  ${name}:`);
		for (const [prop, value] of Object.entries(props)) {
			out.push(`    ${prop}: ${yaml(value)}`);
		}
	}

	out.push("---", "");
	return out.join("\n");
}

function designMd() {
	const current = readFileSync(DESIGN_MD, "utf8");
	if (!FRONT_MATTER.test(current)) {
		throw new Error(
			"DESIGN.md has no front matter block to replace. It must start with a `---` fenced block."
		);
	}
	return current.replace(FRONT_MATTER, frontMatter());
}

// ---------------------------------------------------------------------------

const outputs = [
	[THEME_CSS, themeCss()],
	[DESIGN_MD, designMd()],
];

const check = process.argv.includes("--check");
let stale = 0;

for (const [file, content] of outputs) {
	const relative = path.relative(process.cwd(), file);
	if (check) {
		if (readFileSync(file, "utf8") === content) {
			console.log(`${relative} is up to date.`);
		} else {
			console.error(
				`${relative} is stale. Run \`pnpm -F @securefabric/tokens generate\`.`
			);
			stale += 1;
		}
	} else {
		writeFileSync(file, content);
		console.log(`Wrote ${relative}`);
	}
}

if (stale > 0) {
	process.exit(1);
}
