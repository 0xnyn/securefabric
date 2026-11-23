# Integration logos

Marks of the tools SecureFabric connects to, shown in the catalog, on
integration and connection pages, in the logs and on the hosted connect page.
They're used only to name each tool; the marks belong to their owners.

`src/lib/connector-catalog.ts` (`CONNECTOR_LOGOS`) maps each connector id to a
file here. Every logo sits on a tile that is white in light mode and a faint
lift in dark mode (`ConnectorLogo` in `src/components/kit.tsx`), so coloured
marks read in both themes. A mark that is dark on transparent (GitHub, the AWS
wordmark, UpGuard, Snyk) also ships a `-dark.svg` twin with a light fill, used
in dark mode.

Sources, in order of preference:

1. [svgl](https://svgl.app): full-colour SVGs.
2. [Simple Icons](https://simpleicons.org) (CC0): one-colour SVGs, filled with
   the brand colour Simple Icons records (Okta, Qualys, Snyk, Socket, …).
3. The vendor's own site icon, resized to 64px (shown at 40px at most), where
   neither of the above has the mark (Arnica, Heeler, …).

To add one, drop a square SVG (preferred) or a 64px PNG here, add a `-dark`
twin if the mark disappears on a dark background, and reference it from
`CONNECTOR_LOGOS`. A connector without a logo gets a two-letter monogram.
