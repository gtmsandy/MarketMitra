# Secure Identity Task List

## Checkpoint 1 — CI coverage

- [x] Add `codex/**` push trigger without changing the five jobs.
- [x] Validate, commit, push, and confirm the run starts.

## Checkpoint 2 — Persistence and cryptography

- [x] Add identity ORM models and focused model tests.
- [x] Add reversible migration after `0007`.
- [x] Add Argon2id and opaque-token primitives with tests.
- [x] Test migration upgrade/downgrade on disposable PostgreSQL only.

## Checkpoint 3 — Authentication API

- [x] Register and generic login.
- [x] Session bootstrap, CSRF retrieval, logout, and logout-all.
- [x] Expiry, rotation, revocation, five-session limit, disabled accounts, origin checks, and rate limits.

## Checkpoint 4 — Authorization and administration

- [x] Current-user and require-admin dependencies.
- [x] Profile update and controlled offline admin provisioning.
- [x] Append-only, allowlisted security audit verification.

## Checkpoint 5 — Frontend identity

- [x] Register/login forms and authenticated bootstrap.
- [x] Profile, logout, and protected navigation.
- [x] Protected admin route and expired-session handling.
- [x] Anonymous market routes remain public.

## Checkpoint 6 — Full verification

- [ ] Backend focused and safe suites.
- [x] Disposable PostgreSQL integration suite.
- [x] Frontend tests, lint, type checks, and build.
- [ ] Browser cookie/CORS/CSRF checks.
- [ ] Diff and secret review.
- [ ] Push and inspect five-job CI.
