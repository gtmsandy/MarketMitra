# MarketMitra

MarketMitra is a NEPSE-oriented market analytics platform focused on clear, explainable market intelligence from historical and authorized market data.

## Overview

The application presents market overview metrics, equity breadth, movers, sector performance, a heatmap, stock search, and stock history through a responsive web interface.

## Key capabilities

Implemented capabilities include historical market analytics, common-session equity rankings, sector analytics, heatmap filtering, stock search, stock detail/history, explicit freshness and observation dates, a responsive dashboard, secure cookie sessions with USER/ADMIN authorization, owner-scoped watchlists, an advanced historical screener, and an immutable portfolio ledger with weighted-average cost accounting. The backend uses a provider interface so authorized live feeds can be added without changing frontend API consumers.

The technical-analysis workbench supports candlestick and line views, volume, SMA, EMA, RSI, MACD, Bollinger Bands, timeframe controls, and explicit warm-up/missing-data messaging. The committed 120-session-per-instrument fixture is deterministic and provenance-verified; it is synthetic demonstration data, not NEPSE data.

Planned work is limited to features that require new authorization or product scope, such as licensed real-time feeds, alerts, anomaly detection, corporate-event intelligence, and an explainable AI market assistant.

## Data integrity principles

MarketMitra preserves source-derived observations and does not fabricate financial values. Structurally invalid source observations are excluded from active analytics while their original values remain available for auditability; financial observations are never silently rewritten. Responses expose freshness and observation dates, distinguish market snapshots from equity sessions, and apply explicit security taxonomy so non-equity instruments do not enter equity analytics.

## Architecture

```text
React + TypeScript + Vite
          │ REST API
FastAPI + SQLAlchemy + provider interface
          │
PostgreSQL + Alembic
```

The frontend communicates only with versioned backend APIs. Market data access is isolated behind providers, with PostgreSQL-backed and mock implementations.

## Security taxonomy

Instruments are classified as equity, promoter share, debenture, mutual fund, government bond, or preference share. Equity breadth, movers, sectors, and heatmap analytics filter to common equities so comparisons remain meaningful.

## Identity and portfolio boundaries

Passwords are Argon2id-hashed. Sessions use opaque, hashed verifiers in PostgreSQL and HttpOnly cookies with expiry, revocation, rotation, and CSRF enforcement. Server-side dependencies enforce USER versus ADMIN access, while public market analytics remain anonymous. Watchlists and portfolios are owner-scoped; portfolio transactions are append-only and replayed in deterministic order with Decimal arithmetic, buy fees capitalized, sell fees deducted from proceeds, and insufficient holdings rejected.

## Provenance and demo data

The extended technical fixture is recorded in
`provenance/technical-analysis-manifest.json` and hashes to
`89abb74a6b45ffda12878eb0d12b7bcb99f64135fd02ef84ff0ac286960f4698`.
It contains six fictional instruments, 720 historical OHLCV observations,
and 120 synthetic market snapshots. All UI surfaces label synthetic and
historical observations; no page presents them as live NEPSE quotes.

## Installation

Requirements: Python 3.14, Node.js 24, npm, and PostgreSQL for the PostgreSQL provider.

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

## Configuration

Create `backend/.env` using placeholders:

```env
APP_ENV=development
CORS_ORIGINS=http://localhost:5173
MARKET_DATA_SOURCE=postgres
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<database>
```

Use `MARKET_DATA_SOURCE=mock` when developing without PostgreSQL.

Production uses `APP_ENV=production` and fails startup unless PostgreSQL,
an encrypted remote `DATABASE_URL`, and explicit HTTPS `CORS_ORIGINS` are
configured. `TRUSTED_HOSTS` must also list each public API or health-check host;
wildcards are rejected. Development and test retain local defaults.

Production responses include content-type, referrer, frame and CSP protections.
Set both `HTTPS_DEPLOYMENT=true` and `HSTS_ENABLED=true` only after HTTPS
termination is verified. HTTP limiting uses the direct network peer, exempts
health endpoints, and is intended for one application instance; enforce broader
limits at the trusted reverse proxy. Production WebSockets require an Origin in
`CORS_ORIGINS` and enforce the configured connection cap.

Optional live synchronization is disabled by default. Enable it only with an authorized provider and its documented endpoint/credentials:

```env
LIVE_MARKET_ENABLED=false
LIVE_MARKET_AUTHORIZED=false
NEPSE_PROVIDER_NAME=unconfigured
NEPSE_LIVE_API_URL=
NEPSE_LIVE_API_KEY=
NEPSE_LIVE_API_SECRET=
NEPSE_LIVE_ACCESS_ID=
NEPSE_LIVE_API_VERSION=1.0
LIVE_MARKET_POLL_INTERVAL_SECONDS=1
```

When no live provider is configured, MarketMitra stays explicitly historical or stale rather than presenting historical records as live data.

For local pipeline testing only, use `LIVE_MARKET_ENABLED=true` and `LIVE_MARKET_PROVIDER=replay`. This deterministic `DEVELOPMENT_REPLAY` feed never represents genuine NEPSE data. Authorized providers are delivered through the same canonical state pipeline and WebSocket endpoint (`/api/v1/ws/market`).

## Running the backend

```bash
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health: `http://127.0.0.1:8000/api/v1/health`

Process liveness is available at `/api/v1/health/live`. Runtime readiness is
available at `/api/v1/health/ready` and returns HTTP 503 when required
configuration, database connectivity, or the Alembic revision is not ready.

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

The development interface is served at the Vite URL shown in the terminal.
Production frontend builds require `VITE_API_BASE_URL` to be an explicit HTTPS
API origin; development falls back to `http://127.0.0.1:8000` when it is unset.

## Testing

```bash
cd backend
python -m pytest tests --ignore=tests/test_pre_production_gate.py --ignore=tests/test_postgres_api.py --ignore=tests/test_postgres_identity.py --ignore=tests/test_portfolio_postgres.py --ignore=tests/test_technical_fixture_postgres.py

cd ../frontend
npm ci
npm test
npm run lint
npm run typecheck:app
npm run typecheck:tooling
npm run typecheck:test
npm run build
```

Future historical/demo deployment packaging, environment contracts, provenance
gates, and recovery procedures are documented in [Deployment](docs/deployment.md),
[Data provenance](docs/data-provenance.md), and the [operational runbooks](docs/runbooks/).
These artifacts do not authorize deployment or publication of real market data.

The excluded backend files require an explicitly confirmed disposable
PostgreSQL database. GitHub Actions provisions and seeds that database in a
separate integration job; safe local tests never connect to it implicitly.

## Interview-ready evidence

- `pytest` backend safe suite, PostgreSQL integration, frontend tests, lint,
  TypeScript checks, production build, dependency audit, and deployment-artifact
  verification run in the five-job GitHub Actions workflow.
- Demonstration flow: anonymous dashboard and screener → investor login and
  owner-scoped watchlist → portfolio ledger and cost-basis explanation → admin
  authorization denial for USER → synthetic-data provenance discussion.
- Explain the key tradeoffs: provider isolation, server-side authorization,
  immutable ledger replay, Decimal money calculations, and fail-closed
  historical valuation.

### Resume evidence

- Built a FastAPI/React NEPSE research workspace with PostgreSQL-backed identity,
  RBAC, private watchlists, historical screening, and a provenance-labelled
  technical-analysis workbench.
- Implemented an owner-scoped, append-only portfolio ledger using Decimal
  weighted-average cost accounting, deterministic transaction ordering, and
  concurrency-safe writes.
- Added deterministic synthetic-data ingestion with SHA-256 manifest checks,
  OHLCV validation, idempotent loading, and regression coverage across backend,
  frontend, and PostgreSQL integration paths.

## Project structure

```text
backend/app/api          Versioned HTTP endpoints
backend/app/models       Domain response models
backend/app/providers    Market-data provider implementations
backend/app/repositories Persistence interfaces and adapters
backend/alembic          Database migrations
frontend/src/pages       Dashboard, analytics, and stock views
frontend/src/components  Shared tables, cards, search, and charts
```

## Data sources

Datasets and providers must be obtained and used according to their respective terms and licensing. MarketMitra is an independent project and does not imply official NEPSE affiliation.

## Real-time architecture

The provider interface is designed to support an authorized, licensed real-time feed. Current deployments should be understood according to their configured provider and freshness metadata; the project does not claim production live connectivity by default.

## Future intelligence

Future intelligence features are intended to explain market observations, data provenance, and screening signals. They are educational analytics and do not provide guaranteed investment outcomes or buy/sell advice.

## Disclaimer

MarketMitra provides informational and educational market analytics. Verify information independently and consult a qualified professional before making financial decisions.

## License

No open-source license has yet been specified for this repository.
