# Deployment artifact and environment contract

This document prepares a future historical/demo deployment. It does not
authorize provisioning, publication, or live-market activation.

## Topology

- Build the FastAPI API from the repository-root `Dockerfile`.
- Build the React application separately with `npm ci` and `npm run build`.
  Host only `frontend/dist` on a static HTTPS host/CDN with SPA fallback to
  `index.html`.
- Use an external PostgreSQL service. Do not place PostgreSQL in the API image.
- Run one API worker. Live polling remains disabled.

The API image pins the official `python:3.14.0-slim-bookworm` multi-architecture
index by SHA-256, installs `backend/requirements.txt`, runs as the non-root
`marketmitra` user, includes only the approved provenance artifacts needed for
staging validation, and starts:

```text
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers
```

The command deliberately does not migrate, seed, ingest, or poll. Migrations
are a separate approved one-shot operation described in the migration runbook.

## Reproducible builds and identity

From a clean checkout at an approved commit:

```bash
docker build --pull --tag marketmitra-api:<full-git-sha> .
docker image inspect marketmitra-api:<full-git-sha> --format '{{json .RepoDigests}}'
cd frontend
npm ci
VITE_API_BASE_URL=https://<api-host> npm run build
```

Record the full Git SHA, frontend artifact SHA-256, image tag, and immutable
registry digest in the release record. A mutable tag such as `latest` is not a
release identity. This repository does not publish images automatically.

## Environment and secrets

Start from `deploy/production.env.example` and `deploy/frontend.env.example`.
Required backend values are:

- `APP_ENV=production`
- `MARKET_DATA_SOURCE=postgres`
- `DATABASE_URL` for a remote PostgreSQL database with explicit credentials and
  `sslmode=require`, `verify-ca`, or preferably `verify-full`
- HTTPS-only `CORS_ORIGINS`
- explicit `TRUSTED_HOSTS` for the API and health-check hostnames

`VITE_API_BASE_URL` is required at frontend build time and must be the public
HTTPS API origin. Changing it requires rebuilding the frontend artifact.

Inject database and provider credentials through the deployment platform's
secret store. Never place secrets in an image layer, build argument, manifest,
repository variable, or frontend environment variable. Rotate by creating a
new credential, updating the secret reference, restarting the API, verifying
readiness, then revoking the old credential. Restrict the application database
role to the application schema and required DML; use a separate, temporary
migration role when the platform supports it.

## HTTPS and proxy boundary

Terminate HTTPS at one identified reverse proxy or platform edge. The image
starts Uvicorn with proxy-header processing disabled, so arbitrary clients
cannot influence peer/scheme values. If forwarded-header support becomes
necessary, configure Uvicorn or the platform with an explicit proxy IP
allowlist; never trust all sources.

Enable both `HTTPS_DEPLOYMENT=true` and `HSTS_ENABLED=true` only after the
public HTTPS route, certificate, redirect behavior, and proxy trust are tested.
Preserve application security headers at the edge.

HTTP rate limits and WebSocket caps are per API process. Keep one worker and
apply broader request/connection limits at the trusted edge. Health endpoints
are application-limit exempt and therefore require edge protection.

## Historical/demo data gate

Live polling is disabled by default and must stay disabled for this deployment.
Before loading or publishing a dataset, validate its manifest:

```bash
cd backend
python -m app.scripts.validate_provenance \
  ../provenance/deployment-manifest.json \
  --require-publication-approved
```

Unknown-rights data cannot pass this gate. The committed fixture is fictional,
deterministic staging data and is the only dataset accepted by the staging seed
entry point. After Alembic reaches the reviewed head, run the seed once with an
exact database-name confirmation token:

```bash
MARKETMITRA_CONFIRM_STAGING=<exact-database-name> \
python -m app.scripts.seed_staging_data \
  --manifest /app/provenance/deployment-manifest.json
```

The command rejects local, shared, development, production, unencrypted,
unmigrated, or non-empty targets. It never creates a schema and performs a
rollback-only validation pass before the committed ingestion.

## Pre-release acceptance

Require CI, an actual container build on an available container runtime, a
successful isolated migration, eligible data, readiness, and the smoke checks
from `docs/runbooks/migration-and-rollback.md`. Do not infer financial-data
correctness merely from HTTP 200 responses.
