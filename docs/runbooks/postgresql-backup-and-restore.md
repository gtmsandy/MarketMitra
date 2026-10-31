# PostgreSQL backup and isolated restore runbook

This procedure is documentation, not authorization to access any database.
Commands require an explicitly injected connection secret and verified target.

## Backup policy

- Create a daily PostgreSQL custom-format backup with `pg_dump --format=custom`.
- Retain daily backups for 14 days and monthly recovery points for 3 months as
  an initial portfolio-scale policy; revise after measuring size and recovery
  objectives.
- Store encrypted backups outside the primary database host and account where
  practical, with least-privilege access and deletion protection.
- Record database identifier, UTC start/end, PostgreSQL version, Alembic
  revision, application SHA, backup size, SHA-256, tool exit status, and owner.
- Never place credentials in command arguments, filenames, logs, or manifests.

Example after independently confirming the source database and injecting
`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, and a restricted `PGPASSFILE` from
the platform secret store:

```bash
pg_dump --format=custom --no-owner \
  --file="marketmitra-<utc-timestamp>.dump"
sha256sum "marketmitra-<utc-timestamp>.dump"
pg_restore --list "marketmitra-<utc-timestamp>.dump"
```

An exit code, nonzero size, matching digest after transfer, and readable archive
table of contents are necessary but do not prove restorability.

## Isolated restore exercise

1. Obtain approval and create an empty, disposable PostgreSQL database with a
   unique restore-test name and no network path from public traffic.
2. Verify the resolved host and database name. Require a disposal confirmation
   token tied to that exact name before any drop/replace operation.
3. Download and decrypt a backup into temporary restricted storage; verify its
   recorded SHA-256.
4. Restore without changing the source or any shared database:

```bash
PGSERVICE=marketmitra-disposable-restore pg_restore \
  --no-owner --exit-on-error "<verified-backup>.dump"
```

5. Run `SELECT 1`, compare expected tables/count ranges, check recent market
   snapshot and ingestion timestamps, and verify referential/data constraints.
6. Run `python -m alembic current` against the isolated restore and compare the
   revision with the backup record. Do not automatically upgrade during the
   restore test.
7. Start the matching immutable application artifact against the isolated
   restore and run readiness plus smoke tests.
8. Record recovery time, restored size, revision, consistency results, operator,
   and failures. Escalate any digest, restore, revision, or consistency mismatch.
9. Destroy the disposable target only after exact-name verification and approval.

The first restore exercise establishes measured recovery time; no RTO should be
claimed before then. Data-loss tolerance is bounded by backup frequency unless
the selected PostgreSQL provider supplies separately tested point-in-time
recovery.
