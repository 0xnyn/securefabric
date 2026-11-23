#!/usr/bin/env node
/**
 * Checks every foreground/background pairing the components draw against
 * WCAG 2.2 AA, in both themes, and fails the build if one falls short.
 *
 * A contrast rule in a design document is a promise; a contrast rule in CI
 * is a constraint. If a component needs a pairing that is not listed here,
 * add it here first. That is what makes the conversation happen before the
 * colour ships rather than after.
 *
 * Thresholds: 4.5:1 for text, 3:1 for large text and for the parts of a
 * control that carry its meaning. Hairlines are held to lower floors on
 * purpose: they are quiet by design, but must still be visible.
 *
 * Usage: node scripts/check-contrast.mjs
 */

import { color } from "../src/tokens.ts";

const HEX_PAIRS = [1, 3, 5];

function channels(hex) {
	return HEX_PAIRS.map((offset) =>
		Number.parseInt(hex.slice(offset, offset + 2), 16)
	);
}

function luminance(hex) {
	const [r, g, b] = channels(hex).map((value) => {
		const c = value / 255;
		return c <= 0.040_45 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
	});
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** Lays `hex` at `alpha` over an opaque `under`, as the browser paints it. */
function mix(hex, alpha, under) {
	const top = channels(hex);
	const bottom = channels(under);
	return `#${top
		.map((value, i) =>
			Math.round(value * alpha + bottom[i] * (1 - alpha))
				.toString(16)
				.padStart(2, "0")
		)
		.join("")}`;
}

function ratio(a, b) {
	const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (light + 0.05) / (dark + 0.05);
}

/**
 * Every pairing the components produce. `use` is drawn on `on`. A `tint`
 * background is `tint.role` at `tint.alpha` laid over `on`, which is how
 * `bg-destructive/10` and `bg-ds-success/10` render.
 */
const PAIRINGS = [
	// Text on each surface.
	{ min: 4.5, on: "bg", use: "fg", what: "body text on the page" },
	{ min: 4.5, on: "card", use: "fg", what: "body text on a card" },
	{ min: 4.5, on: "shell", use: "fg", what: "body text on a card shell" },
	{
		min: 4.5,
		on: "surface",
		use: "fg",
		what: "text on a hovered row or secondary button",
	},
	{ min: 4.5, on: "bg", use: "muted", what: "secondary text on the page" },
	{ min: 4.5, on: "card", use: "muted", what: "secondary text on a card" },
	{
		min: 4.5,
		on: "shell",
		use: "muted",
		what: "secondary text on a card shell",
	},
	{
		min: 4.5,
		on: "surface",
		use: "muted",
		what: "secondary text on a subtle fill",
	},

	// The primary, as a fill with text on it and as text itself.
	{ min: 4.5, on: "primary", use: "primaryFg", what: "primary button label" },
	{
		min: 4.5,
		on: "primaryMid",
		use: "primaryFg",
		what: "primary button label under the pointer",
	},
	{
		min: 4.5,
		on: "bg",
		use: "accent",
		what: "link or accent text on the page",
	},
	{ min: 4.5, on: "card", use: "accent", what: "accent text on a card" },
	{ min: 4.5, on: "shell", use: "accent", what: "accent text on a card shell" },
	{ min: 4.5, on: "bg", use: "primary", what: "text-primary on the page" },

	// Status text, plain and on its own tint.
	{ min: 4.5, on: "bg", use: "warnText", what: "error text on the page" },
	{ min: 4.5, on: "card", use: "warnText", what: "error text on a card" },
	{
		min: 4.5,
		on: "bg",
		tint: { alpha: 0.1, role: "warnText" },
		use: "warnText",
		what: "destructive label on its 10% tint",
	},
	{ min: 4.5, on: "bg", use: "successText", what: "success text on the page" },
	{
		min: 4.5,
		on: "bg",
		tint: { alpha: 0.1, role: "success" },
		use: "successText",
		what: "success label on its 10% tint",
	},

	// Code panels.
	{ min: 4.5, on: "code", use: "codeFg", what: "code text" },
	{ min: 4.5, on: "code", use: "codeMuted", what: "code comment" },

	// Non-text: marks that carry state, and the focus ring.
	{
		min: 3,
		on: "bg",
		use: "primary",
		what: "focus ring, checkbox, active mark on the page",
	},
	{ min: 3, on: "card", use: "primary", what: "focus ring on a card" },
	{
		min: 2.2,
		on: "bg",
		use: "success",
		what: "success dot (always beside a text label, so not 3:1)",
	},

	{
		min: 3,
		on: "bg",
		use: "warn",
		what: "error dot or chart mark on the page",
	},

	{
		min: 2.2,
		on: "bg",
		use: "severityHigh",
		what: "high-severity dot (always beside its label)",
	},
	{
		min: 3,
		on: "bg",
		use: "severityMedium",
		what: "medium-severity dot on the page",
	},
	{
		min: 2.2,
		on: "card",
		use: "severityHigh",
		what: "high-severity dot on a card",
	},
	{
		min: 4.5,
		on: "card",
		use: "severityMedium",
		what: "medium-severity status label on a card (the landing demos)",
	},
	{
		min: 4.5,
		on: "card",
		use: "successText",
		what: "success text on a card",
	},

	// Hairlines: quiet by intent, but findable.
	{ min: 1.15, on: "bg", use: "line", what: "hairline on the page" },
	{ min: 1.1, on: "shell", use: "line", what: "hairline on a card shell" },
	{
		min: 1.3,
		on: "bg",
		use: "lineAccent",
		what: "accent hairline on the page",
	},
];

let failures = 0;
const rows = [];

for (const theme of Object.keys(color)) {
	const palette = color[theme];
	rows.push(`\n${theme}`);
	for (const pairing of PAIRINGS) {
		const ground =
			"tint" in pairing
				? mix(
						palette[pairing.tint.role],
						pairing.tint.alpha,
						palette[pairing.on]
					)
				: palette[pairing.on];
		const value = ratio(palette[pairing.use], ground);
		const pass = value >= pairing.min;
		if (!pass) {
			failures += 1;
		}
		const on =
			"tint" in pairing
				? `${pairing.tint.role}/${pairing.tint.alpha * 100} on ${pairing.on}`
				: pairing.on;
		rows.push(
			`${pass ? "  ok  " : " FAIL "} ${value.toFixed(2).padStart(6)}:1 (min ${String(pairing.min).padEnd(4)}) ${pairing.what}  [${pairing.use} on ${on}]`
		);
	}
}

console.log(rows.join("\n"));

if (failures > 0) {
	console.error(
		`\n${failures} pairing${failures === 1 ? "" : "s"} below threshold.`
	);
	process.exit(1);
}

console.log(
	`\nAll ${PAIRINGS.length} pairings pass in ${Object.keys(color).length} themes.`
);
