# Implementation Plan: Local Demo Startup and Technical Analysis

This plan is intentionally separate from the historical secure-identity plan in
`tasks/plan.md`; that file is preserved unchanged.

## Task list

- [ ] Add an explicit demo startup command that loads `.env.demo.local`, verifies the database identity and Alembic head, then starts FastAPI.
- [ ] Add calculation-layer indicators with bounded periods, chronological input handling, warm-up/null output, and deterministic synthetic tests.
- [ ] Extend the existing stock-detail chart with volume, candlestick/close mode, overlays, RSI/MACD panels, controls, provenance and insufficient-data messaging.
- [ ] Add frontend and backend regression coverage without modifying the persistent demo database.
- [ ] Run safe backend, disposable PostgreSQL CI, frontend, browser, lint, build and secret checks; commit and push atomic checkpoints.

## Acceptance criteria

- Demo startup cannot silently select `backend/.env`; it refuses a non-demo database or stale migration before serving.
- Indicators never fabricate warm-up values, use future observations, or emit unsupported recommendations.
- The short persistent fixture displays an explicit insufficient-history state for long-period indicators.
- A separate long synthetic fixture proves indicator accuracy without changing `marketmitra_demo`.
