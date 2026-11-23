# securefabric-domain

The platform's services, one module per area (docs/plan/01-architecture.md, section 2):
tenancy, catalog, vault, connections, sync, records, events, obs, actions, ingress,
enrichment, retention. `apps/api` and `apps/worker` are thin adapters over it.
