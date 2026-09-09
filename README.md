# MarketMitra

MarketMitra is a full-stack market analytics platform for the Nepal Stock Exchange (NEPSE). It provides comprehensive market intelligence, live and historical price tracking, sector rankings, and historical data analytics backed by PostgreSQL.

---

## Architecture

MarketMitra is built as a modular monolith:

```text
React (Vite + TypeScript)
        │
        ▼ (HTTP REST API)
FastAPI Backend (Python 3.11+)
        │
        ├─► MarketService
        │        │
        │        ├─► PostgresMarketProvider (Default / Production)
        │        │        │
        │        │        ├─► PostgresInstrumentRepository
        │        │        ├─► PostgresDailyPriceRepository
        │        │        ├─► PostgresMarketSnapshotRepository
        │        │        └─► PostgresIngestionRunRepository
        │        │
        │        └─► MockMarketProvider (Fallback / Testing)
        │
        ▼
PostgreSQL Database (marketmitra)
```

The frontend communicates solely via backend REST APIs (`/api/v1`). The market data access layer is abstracted behind the `MarketDataProvider` interface, allowing provider swapping without changing API contracts or frontend clients.

---

## Setup & Getting Started

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- PostgreSQL 13+ running locally or accessible via network

### 2. PostgreSQL Setup
Create the target database:
```sql
CREATE DATABASE marketmitra;
```

### 3. Backend Setup & Configuration
From the project root:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env` (see `backend/.env.example`):
```env
CORS_ORIGINS=http://localhost:5173
MARKET_DATA_SOURCE=postgres
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/marketmitra
```

### 4. Database Migrations (Alembic)
Apply database migrations to bring the schema to revision `0003`:
```bash
alembic upgrade head
```

### 5. Historical Data Ingestion
Ingest the NEPSE historical equity dataset and 25-year benchmark index:
```bash
python -m app.scripts.run_ingestion --source csv --file ../data/raw/Nepse_Data --index-file ../data/raw/nepse_index_history.csv --historical --mode insert --json
```

Key ingestion CLI flags:
- `--source csv`: Uses generic CSV data source adapter.
- `--file <path>`: Directory containing sector-organized stock CSVs.
- `--index-file <path>`: Benchmark NEPSE index CSV.
- `--historical`: Enables historical validation mode.
- `--mode insert`: Idempotent ingestion; skips existing `(symbol, date)` pairs.
- `--dry-run`: Validates and parses records without committing database writes.
- `--json`: Outputs structured audit execution report to stdout.

### 6. Start the Backend API
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Verify the health endpoint:
```bash
curl http://127.0.0.1:8000/api/v1/health
```

### 7. Frontend Setup & Startup
From the project root:
```bash
cd frontend
npm install
npm run dev
```
The dashboard will be accessible at `http://localhost:5173`.

---

## Testing & Quality Assurance

### Backend Regression Tests
Run the complete backend test suite (240 tests covering models, routes, providers, repositories, CLI, and pre-production gates):
```bash
cd backend
pytest
```

### Frontend Build & Lint
```bash
cd frontend
npm run lint
npm run build
```

---

## Data Source & Validation Architecture

MarketMitra enforces strict financial data quality rules:
- **Strict Mode (Live/Current):** Enforces canonical OHLC bounds (`high >= open, close`, `low <= open, close`, `high >= low`), Sunday–Thursday trading schedule (rejects Fridays and Saturdays), positive prices, and standard percentage change range `(-100, 1000)`.
- **Historical Mode:** Accommodates known NEPSE market data legacy characteristics while preserving fundamental integrity:
  - Permits legitimate historical Friday trading sessions (Saturdays remain strictly rejected).
  - Permits legacy LTP reporting where LTP/close falls outside High/Low range for debentures or illiquid shares.
  - Accommodates legitimate promoter-share long-gap trades with derived percentage changes up to `+2000%`.
  - Supports 12-character corporate debenture identifiers with underscores (`^[A-Z0-9_]{1,12}$`).
  - **Strictly rejects:** Inverted prices (`high < low`), non-trading Saturday sessions, non-positive prices (`<= 0`), negative volumes, and negative turnovers.
  - **No synthetic fabrication:** Missing historical metrics (`turnover`, `total_volume`, `total_transactions`) remain SQL `NULL` and are never replaced with fabricated zeros.
