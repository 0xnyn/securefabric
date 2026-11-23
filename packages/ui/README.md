# @securefabric/ui

The design system: every control and layout piece the dashboard and the hosted
connect page are built from. It knows nothing about the app or the API; Biome
rejects `@/…`, `next/…` and `@securefabric/client` imports here.

Browse it in Storybook: `pnpm storybook` (http://localhost:6006).

## Layout

| Folder | What lives there | Imports |
|---|---|---|
| `src/primitives` | Vendored shadcn/ui building blocks (sidebar, command, popover, chart, calendar…). Added with `shadcn add` (see `components.json`), kept close to upstream, not linted beyond formatting. | lib, hooks |
| `src/components` | Our curated controls, one concept per file: `button`, `form` (Input, Textarea, Label, Field), `card`, `badge`, `table`, `empty-state`, `dialog` (Dialog, DialogContent, SheetContent), `select`, `switch`, `menu`, `tooltip`, `mono`. Pages use these. | primitives, lib |
| `src/patterns` | Domain-free compositions: `page` (PageHeader, PageBody), `section`, `stat`, `charts`, `copy`, `code`, `tabs`, `key-value`, `avatar`. | components, primitives, lib |
| `src/hooks`, `src/lib` | `use-mobile`, `cn`, number and date formatting. | — |
| `src/styles/globals.css` | Tailwind, the design tokens (`@securefabric/tokens`) and base styles. Imported once by each app. | — |

SecureFabric-aware pieces (connector logos, health badges, query states, role
gating) live in `apps/dash/src/components/domain`, not here.

## Using it

```tsx
import { Button } from "@securefabric/ui/components/button";
import { Card, CardHeader } from "@securefabric/ui/components/card";
import { Section } from "@securefabric/ui/patterns/section";
```

Import from the file, not a barrel. Inside this package, import siblings
relatively.

## Adding a component

1. Pick the layer: a raw building block from shadcn goes in `primitives`
   (`pnpm dlx shadcn add <name>` from this folder); a control pages use goes
   in `components`; a composition of those goes in `patterns`.
2. One concept per file, named after it.
3. Add `<name>.stories.tsx` beside it, with the states that matter (empty,
   loading, error, disabled) and a look at both themes.
4. Controls share one height scale: 28, 32, 36 or 40px (`xs`, `sm`, `md`,
   `lg`), so a row of buttons, inputs and selects lines up.
