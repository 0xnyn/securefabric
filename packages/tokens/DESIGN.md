---
# GENERATED from src/tokens.ts by scripts/generate.mjs. Do not edit this
# block; edit tokens.ts and run `pnpm -F @securefabric/tokens generate`.
version: alpha
name: SecureFabric
description: "SecureFabric's design tokens: navy ink on white, one indigo primary, Inter for prose and UI, a mono for code."
colors:
  accent: "#533afd"
  bg: "#ffffff"
  card: "#ffffff"
  code: "#101116"
  code-fg: "#e8e8e8"
  code-muted: "#868686"
  fg: "#0a2540"
  line: "#e6ebf1"
  line-accent: "#d6d9fc"
  muted: "#606f87"
  primary: "#533afd"
  primary-fg: "#ffffff"
  primary-light: "#b9b9f9"
  primary-mid: "#665efd"
  severity-high: "#fb923c"
  severity-medium: "#9b6829"
  shell: "#fafbfd"
  success: "#15be53"
  success-text: "#0f8138"
  surface: "#f1f4f8"
  warn: "#ea2261"
  warn-text: "#ce1e55"
  dark-accent: "#a99eff"
  dark-bg: "#0a0a0a"
  dark-card: "#0a0a0a"
  dark-code: "#111111"
  dark-code-fg: "#ededed"
  dark-code-muted: "#8f8f8f"
  dark-fg: "#ededed"
  dark-line: "#2e2e2e"
  dark-line-accent: "#3d3d3d"
  dark-muted: "#a1a1a1"
  dark-primary: "#ededed"
  dark-primary-fg: "#0a0a0a"
  dark-primary-light: "#454545"
  dark-primary-mid: "#cccccc"
  dark-severity-high: "#fdba74"
  dark-severity-medium: "#d4a373"
  dark-shell: "#161616"
  dark-success: "#45d483"
  dark-success-text: "#62c073"
  dark-surface: "#1f1f1f"
  dark-warn: "#ff6166"
  dark-warn-text: "#ff6166"
typography:
  2xs:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: 400
    lineHeight: 14px
  xs:
    fontFamily: Inter
    fontSize: 0.75rem
    fontWeight: 400
    lineHeight: 1rem
  code:
    fontFamily: "SF Mono"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 20px
  sm:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: 400
    lineHeight: 1.25rem
  prose:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.7
  base:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.5rem
  lg:
    fontFamily: Inter
    fontSize: 1.125rem
    fontWeight: 400
    lineHeight: 1.75rem
  xl:
    fontFamily: Inter
    fontSize: 1.25rem
    fontWeight: 400
    lineHeight: 1.75rem
  2xl:
    fontFamily: Inter
    fontSize: 1.5rem
    fontWeight: 400
    lineHeight: 2rem
  display-sm:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: -0.02em
  display-md:
    fontFamily: Inter
    fontSize: 36px
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: -0.02em
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: 500
    lineHeight: 1.05
    letterSpacing: -0.025em
  display-xl:
    fontFamily: Inter
    fontSize: 60px
    fontWeight: 500
    lineHeight: 1
    letterSpacing: -0.03em
rounded:
  2xl: 1rem
  3xl: 1.5rem
  4xl: 2rem
  full: 9999px
  lg: 0.5rem
  md: 0.375rem
  sm: 0.25rem
  xl: 0.75rem
  xs: 0.125rem
spacing:
  2xl: 48px
  3xl: 64px
  base: 4px
  gutter: 24px
  lg: 24px
  md: 16px
  section: 96px
  sm: 8px
  xl: 32px
  xs: 4px
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    height: 36px
    padding: "0 16px"
    rounded: "{rounded.full}"
    textColor: "{colors.primary-fg}"
    typography: "{typography.sm}"
  button-primary-dark:
    backgroundColor: "{colors.dark-primary}"
    height: 36px
    padding: "0 16px"
    rounded: "{rounded.full}"
    textColor: "{colors.dark-primary-fg}"
    typography: "{typography.sm}"
  button-primary-hover:
    backgroundColor: "{colors.primary-mid}"
    textColor: "{colors.primary-fg}"
  button-primary-hover-dark:
    backgroundColor: "{colors.dark-primary-mid}"
    textColor: "{colors.dark-primary-fg}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    height: 36px
    padding: "0 16px"
    rounded: "{rounded.full}"
    textColor: "{colors.fg}"
    typography: "{typography.sm}"
  button-secondary-dark:
    backgroundColor: "{colors.dark-surface}"
    height: 36px
    padding: "0 16px"
    rounded: "{rounded.full}"
    textColor: "{colors.dark-fg}"
    typography: "{typography.sm}"
  page:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.fg}"
    typography: "{typography.base}"
  page-dark:
    backgroundColor: "{colors.dark-bg}"
    textColor: "{colors.dark-fg}"
    typography: "{typography.base}"
  page-secondary-text:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.muted}"
  page-secondary-text-dark:
    backgroundColor: "{colors.dark-bg}"
    textColor: "{colors.dark-muted}"
  link:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.accent}"
  link-dark:
    backgroundColor: "{colors.dark-bg}"
    textColor: "{colors.dark-accent}"
  card-shell:
    backgroundColor: "{colors.shell}"
    padding: "{spacing.sm}"
    rounded: "{rounded.3xl}"
    textColor: "{colors.fg}"
  card-shell-dark:
    backgroundColor: "{colors.dark-shell}"
    padding: "{spacing.sm}"
    rounded: "{rounded.3xl}"
    textColor: "{colors.dark-fg}"
  card:
    backgroundColor: "{colors.card}"
    padding: "{spacing.lg}"
    rounded: "{rounded.2xl}"
    textColor: "{colors.fg}"
  card-dark:
    backgroundColor: "{colors.dark-card}"
    padding: "{spacing.lg}"
    rounded: "{rounded.2xl}"
    textColor: "{colors.dark-fg}"
  input:
    backgroundColor: "{colors.bg}"
    height: 36px
    rounded: "{rounded.lg}"
    textColor: "{colors.fg}"
    typography: "{typography.sm}"
  input-dark:
    backgroundColor: "{colors.dark-bg}"
    height: 36px
    rounded: "{rounded.lg}"
    textColor: "{colors.dark-fg}"
    typography: "{typography.sm}"
  error-text:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.warn-text}"
  error-text-dark:
    backgroundColor: "{colors.dark-bg}"
    textColor: "{colors.dark-warn-text}"
  success-text:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.success-text}"
  success-text-dark:
    backgroundColor: "{colors.dark-bg}"
    textColor: "{colors.dark-success-text}"
  status-dot-success:
    backgroundColor: "{colors.success}"
    rounded: "{rounded.full}"
    size: 8px
  status-dot-success-dark:
    backgroundColor: "{colors.dark-success}"
    rounded: "{rounded.full}"
    size: 8px
  status-dot-warn:
    backgroundColor: "{colors.warn}"
    rounded: "{rounded.full}"
    size: 8px
  status-dot-warn-dark:
    backgroundColor: "{colors.dark-warn}"
    rounded: "{rounded.full}"
    size: 8px
  status-dot-high:
    backgroundColor: "{colors.severity-high}"
    rounded: "{rounded.full}"
    size: 8px
  status-dot-high-dark:
    backgroundColor: "{colors.dark-severity-high}"
    rounded: "{rounded.full}"
    size: 8px
  status-dot-medium:
    backgroundColor: "{colors.severity-medium}"
    rounded: "{rounded.full}"
    size: 8px
  status-dot-medium-dark:
    backgroundColor: "{colors.dark-severity-medium}"
    rounded: "{rounded.full}"
    size: 8px
  divider:
    backgroundColor: "{colors.line}"
    height: 1px
  divider-dark:
    backgroundColor: "{colors.dark-line}"
    height: 1px
  divider-accent:
    backgroundColor: "{colors.line-accent}"
    height: 1px
  divider-accent-dark:
    backgroundColor: "{colors.dark-line-accent}"
    height: 1px
  selected-outline:
    backgroundColor: "{colors.primary-light}"
    height: 1px
  selected-outline-dark:
    backgroundColor: "{colors.dark-primary-light}"
    height: 1px
  code-block:
    backgroundColor: "{colors.code}"
    padding: "{spacing.md}"
    rounded: "{rounded.xl}"
    textColor: "{colors.code-fg}"
    typography: "{typography.code}"
  code-block-dark:
    backgroundColor: "{colors.dark-code}"
    padding: "{spacing.md}"
    rounded: "{rounded.xl}"
    textColor: "{colors.dark-code-fg}"
    typography: "{typography.code}"
  code-comment:
    backgroundColor: "{colors.code}"
    textColor: "{colors.code-muted}"
  code-comment-dark:
    backgroundColor: "{colors.dark-code}"
    textColor: "{colors.dark-code-muted}"
---

# SecureFabric Design System

This file follows Google's [DESIGN.md format](https://github.com/google-labs-code/design.md):
the YAML block above holds the tokens in a form agents and design tools can
read, and the prose below says what they are for. The YAML is **generated**
from `src/tokens.ts`, which is the one place values are changed. `src/theme.css`
is generated from the same file, so the CSS, the TypeScript and this document
cannot disagree.

## Overview

SecureFabric is infrastructure for security teams. The people reading its pages
are engineers and security leads: they read terminals, diffs and findings for a
living, and they distrust anything that looks like it is selling harder than
it is showing. So the interface is calm: navy ink on white, generous hairlines,
real product surfaces instead of illustrations, and one indigo that means
"act here".

The same tokens drive every surface in the monorepo:

| Surface | What it uses |
| --- | --- |
| `apps/home` (marketing, docs, blog) | Light by default, dark when the visitor picks it; the `ds-*` utilities, the display type scale |
| `apps/dash` (the product) | Light and dark themes, through the shadcn roles |
| `packages/ui` (shared components) | The shadcn roles, which are mapped onto the `ds-*` roles |

## Colors

Names are roles, not hues: ask for `fg`, not "navy". Each role has a light
value (the brand) and a dark value (`dark-*` above, applied under a `.dark`
ancestor). In CSS a role is `--ds-<role>`; in Tailwind it is `bg-ds-<role>`,
`text-ds-<role>`, `border-ds-<role>`.

Because every role switches with the theme, a component written only in roles
works in both themes with no `dark:` classes. Never paint a surface with a
literal (`bg-white`, `text-[#9b6829]`): it stays light in the dark theme. The
marketing site starts light for everyone and turns dark only when the visitor
picks it with the light/dark switch in the footer; the choice is saved in `localStorage`
under `theme`, the key next-themes uses in the app. The painted wallpapers and
the `code` panel are the same in both themes on purpose.

The dark theme is near-black and neutral, after Vercel's Geist: a `#0a0a0a`
ground, grey hairlines rather than fills, off-white text, and a monochrome
primary (an off-white button with black text). The brand indigo carries on
as `accent`, for links, active marks and the command in a code block.

| Role | Used for |
| --- | --- |
| `bg` | Page ground |
| `fg` | Primary text, headings, strong icons |
| `muted` | Secondary text, captions, list markers, the second half of a two-tone heading |
| `shell` | The outer frame of a card; the content sits on `card` inside it |
| `card` | A card's face, popovers |
| `surface` | Subtle fills: hovered rows, secondary buttons, chips |
| `line` | Hairlines: borders, dividers, table rules, inputs |
| `line-accent` | The hairline around a selected or featured item |
| `primary` | The brand indigo: primary buttons, active states, filled marks |
| `primary-fg` | Text and icons on a `primary` fill |
| `primary-mid` | The primary under the pointer; the middle of a primary gradient |
| `primary-light` | Tinted borders and soft fills. Never text |
| `accent` | The primary as text or a small icon: links, active nav items |
| `warn` / `warn-text` | Errors and findings: `warn` as a dot, fill or chart mark; `warn-text` as words |
| `success` / `success-text` | Fixed or healthy: `success` as a dot or fill; `success-text` as words |
| `severity-high` / `severity-medium` | Finding severity below critical (critical is `warn`), as a dot or bar beside its label. Never text |
| `code` / `code-fg` / `code-muted` | Code panels and terminals. The same in both themes |

**One accent.** Indigo is the only colour that points at something. It means
"this one" or "do this". Don't add a second accent for variety.

**Status colours carry meaning.** In a security product, ruby means a critical
finding, orange high, brown medium, and green fixed. Use them only for state, never as decoration, and
always with a label: colour alone must never be the only signal.

**Marks and text are separate tokens.** `warn` and `success` are tuned for
dots, bars and fills. As text they fail AA, so words use `warn-text` and
`success-text`, which clear 4.5:1 on the page and on their own 10% tint (the
`bg-destructive/10 text-destructive` pattern).

**The shadcn roles are aliases.** `packages/ui` components ask for
`bg-primary`, `text-muted-foreground`, `bg-accent` and so on. `theme.css`
points each at an SecureFabric role (`--muted` is `surface`, `--destructive` is
`warn-text`, `--ring` is `primary`), so components restyle with the tokens and
never need their own palette.

**Illustration colours.** The landing-page scenes use a few colours that are
not roles (the shader wallpaper, the product-shot avatars). They belong to the
artwork, not the interface. Keep them inside the scene that owns them, and
never reuse them for UI.

## Typography

Inter for everything that is read as prose or UI. A mono (`ui-monospace`,
SF Mono on Apple) for code, keys, commands, file paths and figures that should
line up. Apps load Inter and expose it as `--font-inter`; `font-sans` picks it
up from there.

| Step | Size / line height | Used for |
| --- | --- | --- |
| `text-2xs` | 11 / 14 | Dense labels inside product shots and badges |
| `text-xs` | 12 / 16 | Eyebrows, table headers, footnotes |
| `text-code` | 13 / 20 | Inline code, keys, commands (with `font-mono`) |
| `text-sm` | 14 / 20 | UI text, navigation, buttons, captions |
| `text-prose` | 15 / 1.7 | Docs and blog body copy |
| `text-base` | 16 / 24 | Marketing body copy |
| `text-lg` | 18 / 28 | Lead paragraphs |
| `text-xl` | 20 / 28 | Card titles, docs section headings |
| `text-2xl` | 24 / 32 | Small section headings |
| `text-display-sm` | 28 / 1.2 | Feature and card headings |
| `text-display-md` | 36 / 1.15 | Section headings |
| `text-display-lg` | 48 / 1.05 | Page headings |
| `text-display-xl` | 60 / 1 | The home hero, and nothing else |

The display steps carry their own weight (500) and tracking (-0.02em to
-0.03em), so `text-display-md` is the whole heading style in one class. Don't
add `font-medium` or a `tracking-[...]` beside it.

`medium` (500) is the house weight for anything that isn't prose: headings,
labels, buttons. `semibold` is rare. Bold is off-system.

`xs` to `2xl` keep Tailwind's default values on purpose, so existing classes
render the same.

## Layout

Spacing is a 4px grid. Tailwind's spacing utilities multiply it (`p-4` is
16px), and those are the only way to write a gap. The named steps in the YAML
(`sm` 8px, `md` 16px, `lg` 24px...) describe the rhythm for tools that don't
read Tailwind. They aren't separate utilities.

- Marketing sections are separated by `section` (96px). Phones inset content by `gutter` (24px).
- The page column is `max-w-page` (72rem). Long-form reading is `max-w-prose` (42rem).
- Breakpoints are Tailwind's defaults (640, 768, 1024, 1280, 1536).

## Elevation & Depth

Depth comes from layering, not shadows: a `card` on a `shell`, separated by a
`line`. The one shadow, `shadow-float`, is for things that actually lift off
the page, like a floating product shot or a popover. Don't use shadows for
emphasis.

## Shapes

Radii are Tailwind's defaults, shared by every surface:

- Buttons, pills, badges and status dots are `rounded-full`.
- Inputs and small controls are `rounded-lg`. Code panels are `rounded-xl`.
- Cards are `rounded-2xl`. A card shell, or a large panel, is `rounded-3xl`.

A card's shell is one step rounder than its face, so the nested corners stay
concentric.

## Components

The `components` entries in the YAML are the pairs the interface actually
draws. `design.md lint` checks each background/text pair in them for WCAG AA,
alongside `scripts/check-contrast.mjs`. Each has a `-dark` twin.

- **Buttons.** Primary is `primary` with `primary-fg`, `rounded-full`, 36px tall, `text-sm` medium. It moves to `primary-mid` under the pointer. Secondary is `surface` with `fg`. One primary button per view.
- **Cards.** A `shell` frame with 8px of padding around a `card` face. The face has a `line` border.
- **Links.** Inline links in prose are `fg`, underlined in `line`; the underline turns `currentColor` on hover. Standalone links and the active nav item use `accent`.
- **Status.** An 8px `warn`, `severity-high`, `severity-medium` or `success` dot beside a label in `fg`, or the label alone in `warn-text` or `success-text`.
- **Code.** `code` panels with `code-fg` text in `text-code font-mono`, `rounded-xl`. Comments are `code-muted`.

## Do's and Don'ts

**Do**

- Use tokens, not literals. Write `bg-ds-primary`, `text-ds-muted` or `rounded-2xl`, never `bg-[#533afd]` or `text-[15px]`. In TypeScript (OG images, canvas, charts), import from `@securefabric/tokens/tokens`.
- Use the shadcn roles (`bg-primary`, `text-muted-foreground`) inside `packages/ui`, and the `ds-*` roles in app code. Both resolve to the same values.
- Give every interactive component default, hover, focus-visible, active and disabled states.
- Respect `prefers-reduced-motion`: every animation is decorative, so the reduced path is to arrive at the end state.

**Don't**

- Don't add a value that isn't in `tokens.ts`. A new size, colour or radius is a change to the scale, so make it there.
- Don't set text in `warn`, `success` or `primary-light`.
- Don't use status colours for decoration, or colour as the only signal.
- Don't add a second accent colour, a second easing curve, or a third font.
- Don't edit `src/theme.css` or the YAML block above. They are generated, and a hand edit is overwritten by the next run and fails CI until then.

## Motion

One curve for everything: `ease-out-quint` (`cubic-bezier(0.16, 1, 0.3, 1)`),
fast out and a long settle. Three speeds, as CSS variables:
`--ds-duration-fast` (200ms) for colour and opacity, `--ds-duration-base`
(300ms) for hover states and swaps, and `--ds-duration-reveal` (700ms) for
content fading up as it scrolls into view.

## Accessibility

- Target WCAG 2.2 AA.
- Contrast is enforced, not hoped for. `scripts/check-contrast.mjs` checks every text and mark pairing in both themes, laying tints over their real ground before measuring. If a component needs a pairing that isn't listed, add it there first.
- Focus is always visible. The ring is `primary`, which clears 3:1 on every surface.
- Decorative SVG carries `aria-hidden="true"`. A product shot standing in for a screenshot carries `role="img"` and an `aria-label`.

## Working on the tokens

```bash
pnpm -F @securefabric/tokens generate      # regenerate theme.css and this file's YAML
pnpm -F @securefabric/tokens contrast      # contrast report, both themes
pnpm -F @securefabric/tokens check-tokens  # all checks, as CI runs them
```

Change a value in `src/tokens.ts`, run `generate`, and commit all three files.
The generator is deterministic: running it with no token change produces no
diff.

Using the tokens in an app:

```css
@import "tailwindcss";
@import "@securefabric/tokens/theme.css";
```

```ts
import { color } from "@securefabric/tokens/tokens";

color.light.primary; // "#533afd"
```
