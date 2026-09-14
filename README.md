# MarketMitra

MarketMitra is a NEPSE-oriented market analytics platform focused on clear, explainable market intelligence from historical and authorized market data.

## Overview

The application presents market overview metrics, equity breadth, movers, sector performance, a heatmap, stock search, and stock history through a responsive web interface.

## Key capabilities

Implemented capabilities include historical market analytics, common-session equity rankings, sector analytics, heatmap filtering, stock search, stock detail/history, explicit freshness and observation dates, and a responsive dashboard. The backend uses a provider interface so authorized live feeds can be added without changing frontend API consumers.

Planned capabilities include licensed real-time feeds, watchlists, alerts, screening, anomaly detection, corporate-event intelligence, and an explainable AI market assistant.

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

## Installation

Requirements: Python 3.14 or a compatible supported Python version, Node.js compatible with the installed Vite release, npm, and PostgreSQL for the PostgreSQL provider.

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
CORS_ORIGINS=http://localhost:5173
MARKET_DATA_SOURCE=postgres
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<database>
```

Use `MARKET_DATA_SOURCE=mock` when developing without PostgreSQL.

## Running the backend

```bash
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health: `http://127.0.0.1:8000/api/v1/health`

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```

The development interface is served at the Vite URL shown in the terminal.

## Testing

```bash
cd backend
python -m pytest

cd ../frontend
npm run lint
npm run build
```

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
