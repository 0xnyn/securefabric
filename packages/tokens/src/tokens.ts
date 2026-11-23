/**
 * The design tokens: the single source of truth for every SecureFabric surface.
 *
 * Every colour, type size, radius, duration and shadow the interface may use
 * lives here. Two files are generated from this one by `scripts/generate.mjs`:
 *
 * - `src/theme.css`: the CSS custom properties and Tailwind v4 `@theme` block
 *   that `apps/home`, `apps/dash` and `packages/ui` import.
 * - The YAML front matter of `DESIGN.md`, in Google's DESIGN.md format, so
 *   agents and design tools read the same values the CSS does.
 *
 * Change a value here, run `pnpm -F @securefabric/tokens generate`, and commit all
 * three. CI fails if a generated file is stale. DESIGN.md explains what each
 * token is for; this file is the authority on its value.
 *
 * Node imports this file directly (type stripping), so it must stay plain
 * data: no enums, no namespaces, no imports.
 */

/**
 * Colour roles. Names are roles, not hues: `fg` is "the text colour", not
 * "navy". Each role has a light value (the brand, and the default everywhere)
 * and a dark value (used under `.dark`, when the viewer picks dark mode). A
 * component asks for a role and gets the right value in either theme.
 *
 * CSS: `--ds-<role>` (e.g. `--ds-line-accent`), Tailwind: `bg-ds-<role>`.
 */
export const color = {
	/**
	 * Dark is near-black and neutral, in the manner of Vercel's Geist: a
	 * `#0a0a0a` ground, grey hairlines instead of fills, off-white text, and a
	 * monochrome primary (an off-white button with black text). The brand
	 * indigo stays on as `accent`, for links and active marks, so the theme
	 * still reads as SecureFabric.
	 */
	dark: {
		accent: "#a99eff",
		bg: "#0a0a0a",
		card: "#0a0a0a",
		code: "#111111",
		codeFg: "#ededed",
		codeMuted: "#8f8f8f",
		fg: "#ededed",
		line: "#2e2e2e",
		lineAccent: "#3d3d3d",
		muted: "#a1a1a1",
		/** Monochrome: the primary button is off-white, and `text-primary` reads as plain bright text. */
		primary: "#ededed",
		/** Black text on the off-white primary. */
		primaryFg: "#0a0a0a",
		primaryLight: "#454545",
		primaryMid: "#cccccc",
		severityHigh: "#fdba74",
		severityMedium: "#d4a373",
		shell: "#161616",
		success: "#45d483",
		successText: "#62c073",
		surface: "#1f1f1f",
		warn: "#ff6166",
		warnText: "#ff6166",
	},
	light: {
		/** The primary used as text or a small icon on `bg`. */
		accent: "#533afd",
		/** Page ground. */
		bg: "#ffffff",
		/** A card's face, and popovers. */
		card: "#ffffff",
		/** Code panels: near-black with a faint indigo cast. Same in both themes. */
		code: "#101116",
		/** Text in a code panel. */
		codeFg: "#e8e8e8",
		/** Comments and secondary text in a code panel. */
		codeMuted: "#868686",
		/** Primary text, headings, strong icons. A deep navy rather than black. */
		fg: "#0a2540",
		/** Hairlines: borders, dividers, table rules, inputs at rest. */
		line: "#e6ebf1",
		/** A hairline tinted toward the primary, for the selected or featured item. */
		lineAccent: "#d6d9fc",
		/**
		 * Secondary text, captions, list markers, the muted half of a heading.
		 * Deep enough to clear 4.5:1 on `surface` as well as on `bg`.
		 */
		muted: "#606f87",
		/** The brand indigo. Primary buttons, active states, filled marks. */
		primary: "#533afd",
		/** Text and icons on a `primary` fill. */
		primaryFg: "#ffffff",
		/** The pale end of the primary: tinted borders, soft fills. Never text. */
		primaryLight: "#b9b9f9",
		/** The primary under the pointer, and the middle of a primary gradient. */
		primaryMid: "#665efd",
		/**
		 * Finding severity, as a dot or bar beside its label. Critical is `warn`;
		 * these are the next two steps down. Never text.
		 */
		severityHigh: "#fb923c",
		/**
		 * Medium-severity findings, as a dot or bar beside its label, or as a
		 * short status label on a card (clears 4.5:1 there).
		 */
		severityMedium: "#9b6829",
		/** The outer shell of a card; the content sits on `card` inside it. */
		shell: "#fafbfd",
		/** A healthy or completed state, as a dot or fill. Never text. */
		success: "#15be53",
		/** A healthy or completed state as text; clears 4.5:1 on its 10% tint. */
		successText: "#0f8138",
		/** Subtle fills: hovered menu rows, secondary buttons, inline chips. */
		surface: "#f1f4f8",
		/** Errors and warnings as a dot, fill or chart mark. Never text: use `warnText`. */
		warn: "#ea2261",
		/**
		 * Errors, destructive actions and warnings as text. A deeper ruby than
		 * `warn`, so it clears 4.5:1 on the page and on its own 10% tint.
		 */
		warnText: "#ce1e55",
	},
} as const;

/**
 * Type. One sans for everything that is read as prose or UI, one mono for
 * code, keys, commands and figures. Apps load Inter themselves and expose it
 * as `--font-inter`; the stack falls back to the named family if they don't.
 */
export const font = {
	family: {
		mono: 'ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace',
		sans: 'var(--font-inter, "Inter"), ui-sans-serif, system-ui, sans-serif',
	},
	/** The family names alone, for tools that cannot read a CSS stack. */
	name: {
		mono: "SF Mono",
		sans: "Inter",
	},
	tracking: {
		/** Display headings. */
		display: "-0.02em",
		/** Section and card headings. */
		heading: "-0.01em",
	},
	weight: {
		/** Headings, labels, buttons, emphasis. The house weight for anything that is not prose. */
		medium: "500",
		/** Body copy. */
		regular: "400",
		/** Rare: a figure that has to carry a panel. */
		semibold: "600",
	},
} as const;

/**
 * The type scale, smallest first. Each step pairs a size with its line height;
 * display steps also carry their weight and tracking, so `text-display-md` is
 * the whole heading style in one class.
 *
 * `xs`, `sm`, `base`, `lg`, `xl` and `2xl` keep Tailwind's default values on
 * purpose, so existing classes keep rendering the same. The other steps name
 * sizes the site was already using as one-offs (`text-[13px]`, `text-[36px]`).
 *
 * `family: "mono"` marks a step meant for the mono family (used by DESIGN.md);
 * in CSS the family is still set with `font-mono`.
 */
export const text = {
	"2xl": {
		fontSize: "1.5rem",
		lineHeight: "2rem",
		use: "Small section headings",
	},
	"2xs": {
		fontSize: "11px",
		lineHeight: "14px",
		use: "Dense labels inside product shots and badges",
	},
	base: { fontSize: "1rem", lineHeight: "1.5rem", use: "Marketing body copy" },
	code: {
		family: "mono",
		fontSize: "13px",
		lineHeight: "20px",
		use: "Inline code, keys, commands",
	},
	"display-lg": {
		fontSize: "48px",
		fontWeight: "500",
		letterSpacing: "-0.025em",
		lineHeight: "1.05",
		use: "Page headings",
	},
	"display-md": {
		fontSize: "36px",
		fontWeight: "500",
		letterSpacing: "-0.02em",
		lineHeight: "1.15",
		use: "Section headings",
	},
	"display-sm": {
		fontSize: "28px",
		fontWeight: "500",
		letterSpacing: "-0.02em",
		lineHeight: "1.2",
		use: "Feature and card headings",
	},
	"display-xl": {
		fontSize: "60px",
		fontWeight: "500",
		letterSpacing: "-0.03em",
		lineHeight: "1",
		use: "The home hero, and nothing else",
	},
	lg: { fontSize: "1.125rem", lineHeight: "1.75rem", use: "Lead paragraphs" },
	prose: {
		fontSize: "15px",
		lineHeight: "1.7",
		use: "Docs and blog body copy",
	},
	sm: {
		fontSize: "0.875rem",
		lineHeight: "1.25rem",
		use: "UI text, navigation, buttons, captions",
	},
	xl: {
		fontSize: "1.25rem",
		lineHeight: "1.75rem",
		use: "Card titles, docs section headings",
	},
	xs: {
		fontSize: "0.75rem",
		lineHeight: "1rem",
		use: "Eyebrows, table headers, footnotes",
	},
} as const;

/**
 * Spacing. A 4px grid: Tailwind's spacing utilities multiply `base`, so `p-4`
 * is 16px. The named steps are the ones layouts should reach for; they are
 * documented in DESIGN.md but not emitted as utilities, so there is one way
 * to write a gap, not two.
 */
export const space = {
	"2xl": "48px",
	"3xl": "64px",
	base: "4px",
	/** Horizontal page inset on phones. */
	gutter: "24px",
	lg: "24px",
	md: "16px",
	/** Vertical rhythm between marketing sections. */
	section: "96px",
	sm: "8px",
	xl: "32px",
	xs: "4px",
} as const;

/**
 * Corner radii. Tailwind's default values, made explicit so every surface
 * shares them. Controls are pills (`full`), cards are `2xl`, large panels `3xl`.
 */
export const radius = {
	"2xl": "1rem",
	"3xl": "1.5rem",
	"4xl": "2rem",
	full: "9999px",
	lg: "0.5rem",
	md: "0.375rem",
	sm: "0.25rem",
	xl: "0.75rem",
	xs: "0.125rem",
} as const;

/** Content widths. CSS: `--container-<name>`, Tailwind: `max-w-<name>`. */
export const layout = {
	/** The page column every marketing section centres on. */
	page: "72rem",
	/** Long-form reading measure: docs, blog, legal. */
	prose: "42rem",
} as const;

/**
 * Motion. One curve for everything that moves, so unrelated components
 * decelerate the same way.
 */
export const motion = {
	duration: {
		/** Hover states, tab swaps, icon rotation. */
		base: "300ms",
		/** Colour and opacity changes on a control. */
		fast: "200ms",
		/** Content fading up as it scrolls into view. */
		reveal: "700ms",
	},
	/** Fast out, long settle. */
	ease: "cubic-bezier(0.16, 1, 0.3, 1)",
} as const;

/** Elevation. Used only for surfaces that actually lift off the page. */
export const shadow = {
	/** A floating product shot or popover. */
	float: "0 8px 30px -12px rgb(0 0 0 / 0.18)",
} as const;

export type Theme = keyof typeof color;
export type ColorToken = keyof typeof color.light;
export type TextToken = keyof typeof text;
export type RadiusToken = keyof typeof radius;
