# Migration, release, and rollback runbook

This runbook requires an approved isolated target. It never authorizes changes
to a developer, shared, staging, or production database by itself.

## 1. Pre-deployment gate

1. Record change approval, Git SHA, image digest, frontend artifact digest,
   database target identifier, owner, maintenance window, and rollback owner.
2. Confirm the database hostname and name independently. Stop if either is
   ambiguous or points to a developer/shared database.
3. Require green CI, dependency audits, an actual image build, provenance
   approval, and a tested backup/restore procedure.
4. Confirm `LIVE_MARKET_ENABLED=false` and that no startup command runs seed,
   ingestion, `create_all`, or Alembic.
5. Record current application version and Alembic revision:
   `python -m alembic current` using the explicitly injected target URL.

## 2. Backup checkpoint

Complete `docs/runbooks/postgresql-backup-and-restore.md`. Record the encrypted
backup URI, SHA-256, database revision, start/end time, and verification result.
Do not continue without a restorable backup and named recovery approver.

## 3. Migration preparation

1. Review every revision between current and target heads.
2. Classify locks, table rewrites, data loss, and downgrade limitations.
3. Obtain explicit approval for destructive or irreversible operations.
4. Test upgrade on an isolated restored copy and run consistency checks.
5. Record the expected Alembic head from `python -m alembic heads`.

## 4. One-shot migration

Scale/stop application writers if the reviewed migration requires it. From the
approved API artifact, run exactly one migration task with the target secret:

```bash
python -m alembic upgrade head
python -m alembic current
```

The reported current revision must equal the reviewed head. Never put this
command in API startup or run multiple migration tasks concurrently.

## 5. Release and verification

1. Start the SHA/digest-pinned API image with one worker.
2. Publish the separately verified frontend artifact.
3. Confirm `/api/v1/health/live`, then `/api/v1/health/ready`.
4. Run the bounded smoke test only against the explicitly approved target:

```bash
python -m app.scripts.smoke_test \
  --api-base-url https://<api-host> \
  --frontend-url https://<frontend-host> \
  --allow-remote
```

Enable the WebSocket check only in a permitted test environment by adding
`--websocket --websocket-origin https://<frontend-host>`.

## 6. Failed-start diagnosis

Keep traffic on the prior version. Check generic application logs, environment
validation, database reachability/TLS, pool exhaustion, Alembic revision, host
and origin configuration, and health responses. Do not print the database URL
or secret values. A liveness success with readiness failure means the process
is running but configuration, database, or migration readiness is not met.

## 7. Application rollback

If the schema remains backward-compatible, redeploy the prior immutable API and
frontend artifacts, verify readiness, and rerun smoke tests. Application
rollback does not imply that `alembic downgrade` is safe.

Never downgrade a schema merely to match an old application. For an incompatible
or destructive migration, stop writes and escalate to the database recovery
owner. Choose a reviewed forward fix or isolated backup restoration. Both need
explicit approval, a downtime/data-loss assessment, and an audit record.
