# Backup restore drill

**Cadence:** quarterly and after any change to the schema, roles or vault layout (NFR-08).
**Run:** `make drill-restore` (`tools/drills/restore_drill.py`).

## What it proves

A backup is only a backup once it has been restored. The drill dumps the database with
`pg_dump -Fc`, restores it into a fresh scratch database, and checks that the copy is usable,
not just present:

1. **Migrations:** every migration is recorded and its checksum matches the file on disk
   (the migration runner refuses a mismatch, so a restore from a diverged branch shows here).
2. **Data:** row counts of the core tables match the source.
3. **Isolation:** row-level security is still enabled on the tenant tables, with its policies.
4. **Vault:** a sealed credential opens with the KEK from the environment. This proves the
   wrapped environment keys came back intact and that the deployment's KEK still matches
   them. A restore without the matching `VAULT_MASTER_KEY` produces a database whose
   credentials are unreadable: customers would have to reconnect every connection.

The source database is only read; the scratch database is dropped at the end.

## Production

Production relies on point-in-time recovery, not dumps. Run the same checks against a PITR
restore into a new instance: point `DATABASE_URL` at it and run the verification half of the
drill (steps 1 to 4). Record the time to restore, the recovery point and the result in the
operations log.

## If it fails

- **Migrations pending or mismatched:** the backup predates a migration, or the restore ran
  migrations from a different branch. Restore the matching release.
- **Counts differ:** the dump was taken while writes were happening and is still consistent
  (pg_dump takes a snapshot); differences point at a partial restore. Re-run with
  `--exit-on-error` output in view.
- **Credential does not open:** wrong `VAULT_MASTER_KEY` for this database. Find the key
  version that wrapped the environment keys before going further.
