# Secure Identity Task List

## Checkpoint 1 — CI coverage

- [ ] Add `codex/**` push trigger without changing the five jobs.
- [ ] Validate, commit, push, and confirm the run starts.

## Checkpoint 2 — Persistence and cryptography

- [ ] Add identity ORM models and focused model tests.
- [ ] Add reversible migration after `0007`.
- [ ] Add Argon2id and opaque-token primitives with tests.
- [ ] Test migration upgrade/downgrade on disposable PostgreSQL only.

## Checkpoint 3 — Authentication API

- [ ] Register and generic login.
- [ ] Session bootstrap, CSRF retrieval, logout, and logout-all.
- [ ] Expiry, rotation, revocation, five-session limit, disabled accounts, origin checks, and rate limits.

## Checkpoint 4 — Authorization and administration

- [ ] Current-user and require-admin dependencies.
- [ ] Profile update and controlled offline admin provisioning.
- [ ] Append-only, allowlisted security audit verification.

## Checkpoint 5 — Frontend identity

- [ ] Register/login forms and authenticated bootstrap.
- [ ] Profile, logout, and protected navigation.
- [ ] Protected admin route and expired-session handling.
- [ ] Anonymous market routes remain public.

## Checkpoint 6 — Full verification

- [ ] Backend focused and safe suites.
- [ ] Disposable PostgreSQL integration suite.
- [ ] Frontend tests, lint, type checks, and build.
- [ ] Browser cookie/CORS/CSRF checks.
- [ ] Diff and secret review.
- [ ] Push and inspect five-job CI.
