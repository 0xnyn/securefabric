# securefabric-db

- `DatabaseSettings` (`DATABASE_*`) and `create_pool()`: async psycopg pool with autocommit connections. `ping()` backs the readiness check.
- `securefabric-migrate`: forward-only SQL migrations from `db/migrations`. Tracks checksums and takes an advisory lock. Use `--status` to list applied migrations.
