# Extended synthetic technical-analysis fixture

`provenance/fixtures/marketmitra-synthetic-technical-analysis-v1.json` is a
separate, deterministic engineering fixture. It contains 120 generated
Monday-Friday sessions for each of the six fictional `SYN*` instruments (720
generated price rows and 120 generated snapshots). It is not NEPSE data and it
does not model the official NEPSE holiday calendar.

The generator is `backend/app/scripts/generate_technical_fixture.py` with seed
`20261109` and version `technical-fixture-generator-v1`. It verifies the
original v1 fixture digest before generation and embeds the original 24 price
observations and four snapshots as an immutable preservation record. The
original fixture file is never rewritten.

The manifest is
`provenance/technical-analysis-manifest.json`. Its SHA-256 digest is validated
before loading. The loader checks instrument identity, deterministic metadata,
weekday-only generated sessions, chronological ordering, duplicate keys,
positive OHLC values, OHLC bounds, non-negative activity, and baseline equality.

## Disposable import procedure

The import command is dry-run by default and accepts only a runner-local
PostgreSQL database whose name ends in `_ci`. It verifies `current_database()`
and `current_user`, the Alembic head, baseline rows, generated-row overlap, and
the checksum before any commit:

```powershell
cd backend
$env:DATABASE_URL = '<disposable PostgreSQL URL ending in _ci>'
$env:MARKETMITRA_CONFIRM_DISPOSABLE = '<same database name>'
.\.venv\Scripts\python.exe -m app.scripts.ingest_technical_fixture
```

After reviewing the dry-run report, the disposable target can be explicitly
authorized for insertion:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.ingest_technical_fixture --apply
```

The command rejects `marketmitra_demo`, `marketmitra_auth_ci`, `marketmitra`,
`postgres`, and `vinay_clinic`; it does not accept a demo database as a
shortcut. Re-running against the same disposable target is idempotent: exact
existing generated rows are skipped, while altered overlaps are rejected.

## Persistent demo import proposal (not executed)

`marketmitra_demo` was intentionally not modified. A future import would
require a separate explicit approval, a fresh protected backup, re-verification
of the database identity and Alembic `0009`, baseline row and watchlist/user
preservation checks, a dry-run overlap report, and a post-import count and
authentication verification. The current command deliberately blocks that
target; no persistent-demo procedure has been executed.
