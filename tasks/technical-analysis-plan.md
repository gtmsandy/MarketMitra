# Implementation Plan: Local Demo Startup and Technical Analysis

This plan is intentionally separate from the historical secure-identity plan in
`tasks/plan.md`; that file is preserved unchanged.

## Task list

- [x] Add an explicit demo startup command that loads `.env.demo.local`, verifies the database identity and Alembic head, then starts FastAPI.
- [x] Add calculation-layer indicators with bounded periods, chronological input handling, warm-up/null output, and deterministic synthetic tests.
- [x] Extend the existing stock-detail chart with volume, candlestick/close mode, overlays, RSI/MACD panels, controls, provenance and insufficient-data messaging.
- [x] Add frontend and backend regression coverage without modifying the persistent demo database.
- [x] Run safe backend, disposable PostgreSQL CI, frontend, browser, lint, build and secret checks; commit and push atomic checkpoints.

## Extended fixture phase

- [ ] Generate a separate deterministic, synthetic, weekday-only technical-analysis fixture while preserving the original fixture as an immutable baseline.
- [ ] Add provenance and validation tests for determinism, OHLCV integrity, uniqueness, chronology, and manifest digest.
- [ ] Add a dry-run-first ingestion preflight that verifies the target identity, schema head, checksum, baseline overlap, and idempotency without touching `marketmitra_demo`.
- [ ] Verify indicator outputs and chart behavior against the extended fixture using disposable database/in-memory test data only.

## Acceptance criteria

- Demo startup cannot silently select `backend/.env`; it refuses a non-demo database or stale migration before serving.
- Indicators never fabricate warm-up values, use future observations, or emit unsupported recommendations.
- The short persistent fixture displays an explicit insufficient-history state for long-period indicators.
- A separate long synthetic fixture proves indicator accuracy without changing `marketmitra_demo`.
