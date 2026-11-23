# securefabric-domain

The control-plane domain behind the dash: the workspace (team, members), its
environments, and everything an environment holds (API keys, webhooks,
variables, integrations, connections, sync jobs, operations/logs).

- `models.py`: the pydantic schemas. They mirror what `apps/dash` renders, camelCase on the wire, and become `@securefabric/client` types through OpenAPI.
- `catalog.py`: the provider catalog, read from `catalog.json`. That file is generated from `apps/dash/src/lib/catalog.ts` (`make generate`) and `check-catalog` guards it.
- `repository.py`: Postgres reads and writes (`db/migrations/0002_control_plane.sql`).
- `service.py`: the operations the dash performs, as transactions. Syncs only *start* here. The worker finishes them as durable `sync-connection` tasks.
- `seed.py`: the demo workspace (`make seed`).
