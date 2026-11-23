# SecureFabric documentation

| Section | What is there |
|---|---|
| [Architecture](architecture/README.md) | The as-built architecture in ten parts: system context, tenancy and security, data model, sync engine, connector platform, connections and connect, API and events, dashboard and clients, operations, and decisions, status and roadmap. **Start here** to understand how the system works, what each guarantee rests on, and what is still open. |
| **API reference** | The OpenAPI document is generated from the code: `GET /openapi.json` on the API, Swagger UI at `/docs`, and `make openapi` writes `openapi.json`. The typed TypeScript client in `packages/client` is generated from it. |
| [Guides](guides/) | [Receiving webhooks](guides/webhooks.md) (verification samples in Python, Node, Go and Ruby, tested in CI) · [Migrating from Leen V2](guides/leen-migration.md) |
| [Connectors](connectors/) | Generated reference pages, one per connector: auth, permissions, streams, options, the values each stream emits and the vendor-to-canonical mapping tables ([GitHub](connectors/github.md), [SANDBOX](connectors/sandbox.md)). Regenerate with `make docs-connectors`; CI fails when a page is stale. |
| [Runbooks](runbooks/) | One page per operator alert and per connection health code, plus the backup restore drill. |
| [Plan](plan/00-README.md) | The design, parts 00–10. Build status is in [`progress.md`](../progress.md). |
| [Research](research/) | Facts gathered from vendor documentation that the build relies on. |
