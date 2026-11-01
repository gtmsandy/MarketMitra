# Implementation Plan: Secure Identity Foundation

## Overview

Continue on `codex/product-refinement-stage-a`, first enabling the existing five-job CI workflow for `codex/**` pushes, then implementing PostgreSQL-backed USER/ADMIN identity in independently verified checkpoints. Public market analytics remain anonymous. No main merge, deployment, portfolio schema, live provider, or existing database mutation is in scope.

## Architecture Decisions

- Keep identity inside the existing FastAPI modular monolith with explicit API schemas, services, repositories, and dependencies.
- Store only SHA-256 verifiers for 256-bit session and CSRF secrets; raw values exist only at the browser boundary.
- Use Argon2id through a pinned maintained library with reviewed parameters and bounded password byte length.
- Use additive Alembic tables after verified head `0007`; migration upgrade/downgrade runs only against an explicitly confirmed disposable PostgreSQL database ending in `_ci`.
- Use credentialed CORS only for explicit origins. The session cookie covers `/api/v1` so future authenticated watchlist, portfolio, and admin routes receive it.
- Keep incomplete identity UI unreachable until its backend contract and tests are complete.

## Task List

### Checkpoint 1: CI coverage

- [ ] Permit pushes to `codex/**` in the existing workflow without changing any job.
- [ ] Validate the workflow diff, commit, push, and confirm all five jobs start.

### Checkpoint 2: Identity persistence and cryptography

- [ ] Add tested user, session, and append-only audit ORM contracts.
- [ ] Add one reversible Alembic revision from verified head `0007`.
- [ ] Add Argon2id password and opaque-token primitives with focused tests.
- [ ] Verify upgrade and downgrade only on a disposable PostgreSQL database.

### Checkpoint 3: Registration and session API

- [ ] Add stable request, response, and error contracts.
- [ ] Implement USER-only registration, generic login, session bootstrap, CSRF retrieval, logout, and logout-all.
- [ ] Enforce expiry, rotation, revocation, five-session limit, disabled accounts, origin checks, and bounded auth rate limits.

### Checkpoint 4: Authorization and administration

- [ ] Add current-user and require-admin dependencies with server-side tests.
- [ ] Add safe profile update and controlled offline admin provisioning.
- [ ] Verify audit events contain no raw credentials, tokens, CSRF values, or private financial data.

### Checkpoint 5: Frontend identity flow

- [ ] Add register/login pages, validated session bootstrap, logout, and profile UI.
- [ ] Add protected user/admin navigation with loading and expired-session states.
- [ ] Preserve anonymous market routes and use credentialed requests only where required.

### Checkpoint 6: Final verification

- [ ] Run focused and full backend suites.
- [ ] Run disposable PostgreSQL migration and integration tests.
- [ ] Run frontend tests, lint, all TypeScript checks, build, and browser checks.
- [ ] Scan the final diff for unrelated files, generated artifacts, and secrets.
- [ ] Push verified checkpoints and inspect all five CI jobs.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Raw session or CSRF secret leaks | High | Store only digests; redact errors/audits; add negative tests and secret scans. |
| Cookie unavailable to future protected APIs | High | Use `Path=/api/v1`, not an auth-only path. |
| Cross-origin development fails | Medium | Explicit loopback origins, `allow_credentials=True`, bounded methods/headers, browser verification. |
| Migration targets a real database | High | Require runner-local PostgreSQL, `_ci` suffix, and exact confirmation variable before any mutation. |
| Partial auth becomes reachable | High | Keep navigation and routes gated until backend and frontend slice is complete. |
| In-memory rate limits do not scale | Medium | Document single-instance scope and require proxy/shared enforcement before multi-instance deployment; deployment is out of scope. |

## Open Questions

None. The user-approved security contract resolves the implementation-sensitive choices needed for this branch.
