# Integration logos

Marks of the tools Airship connects to, shown on `/integrations`, the use-case
pages and the product mocks (`src/components/integrations/IntegrationLogo.astro`).
They're used only to name each tool; the marks belong to their owners.

Each file name matches the `logo` field in `src/copy/integrations.ts`. Sources, in
order of preference:

1. [svgl](https://svgl.app): full-colour SVGs (AWS, Azure, Google Cloud, GitHub,
   GitLab, Slack, Datadog, Microsoft products, and others).
2. [Simple Icons](https://simpleicons.org) (CC0): one-colour SVGs, filled with the
   brand colour Simple Icons records (Okta, Qualys, Snyk, Jira, and others).
3. The vendor's own site icon (apple-touch-icon or SVG favicon), resized to 64px (shown at 28px at most),
   where neither of the above has the mark.

To add one, drop a square SVG (preferred) or a 64px PNG here and reference it
from `src/copy/integrations.ts`.
