# MarketMitra local interview demo

The persistent interview demo uses the isolated PostgreSQL database
`marketmitra_demo` and role `marketmitra_demo_user`. The existing
`backend/.env` (the `marketmitra` database) and `backend/.env.auth-ci.local`
(the disposable CI database) are not changed by these instructions.

## Start locally

Run the backend and frontend in separate PowerShell windows from the repository
root:

```powershell
Push-Location .\backend
.\.venv\Scripts\python.exe -m app.scripts.start_demo --env-file .env.demo.local --host 127.0.0.1 --port 8000
```

```powershell
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
Push-Location .\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Open <http://127.0.0.1:5173>. Use the matching `127.0.0.1` origin for
authenticated flows; mixing `localhost` and `127.0.0.1` intentionally does not
share the session cookie.

The startup helper loads only `backend/.env.demo.local`, performs read-only
checks for `marketmitra_demo`, `marketmitra_demo_user`, and Alembic `0010`, and
refuses to start if any identity differs. It prints no connection string or
credential. After startup, verify <http://127.0.0.1:8000/api/v1/health/live>
and <http://127.0.0.1:8000/api/v1/health/ready> before opening the frontend.

## Demo accounts

- Investor: `investor@marketmitra.test`
- Admin: `admin@marketmitra.test`
- Credential Manager entries: `MarketMitra/demo-investor`,
  `MarketMitra/demo-admin`, and `MarketMitra/marketmitra_demo`

Passwords are stored only in Windows Credential Manager. Never put them in the
repository, an environment file, a fixture, or documentation.

## Interview walkthrough

1. Show the anonymous market overview, movers, sectors, heatmap and synthetic-data provenance.
2. Sign in as the investor and open the profile.
3. Update the display name, refresh, and show session persistence.
4. Open the admin endpoint/page as the investor to demonstrate server-side denial.
5. Sign out and confirm protected requests are rejected.
6. Sign in as the admin and show the server-verified admin page.
7. Sign out before closing the demo.

## Watchlist walkthrough

1. While signed in as the investor, open **Watchlists** and create
   `My NEPSE Watchlist`.
2. Search for `SYNBANKA` and `SYNBANKB`, adding both synthetic securities.
3. Refresh the page, then sign out and sign back in to demonstrate that the
   private list and its items persist in `marketmitra_demo`.
4. Sign in as the admin and open Watchlists; the investor's private list must
   not appear, demonstrating owner-scoped isolation.
5. From a stock detail page, use **Add to watchlist** and confirm the item
   appears in the investor list. Keep the `HISTORICAL` and synthetic labels
   visible when discussing the data provenance.

## Portfolio walkthrough

1. Sign in as `investor@marketmitra.test`, open **Portfolio**, and create or
   select `MarketMitra Demo Portfolio`.
2. Record the following hypothetical SYNBANKA transactions with unique
   idempotency keys: buy 10 at NPR 100 with NPR 5 fees on 2026-09-06; buy 5 at
   NPR 110 with NPR 5 fees on 2026-09-07; and sell 4 at NPR 120 with NPR 2 fees
   on 2026-09-08.
3. Explain that buy fees are capitalized. The NPR 1,560 acquisition cost over
   15 shares produces a weighted-average cost of NPR 104. The sale removes NPR
   416 of cost and realizes NPR 62 after its fee, leaving 11 shares with NPR
   1,144 carrying cost.
4. Show realized and unrealized P&L, the actual price-observation date, and the
   `synthetic` / `historical` provenance labels. Do not describe the valuation
   as current market data.
5. Refresh, then sign out and back in to demonstrate persistence. Sign in as a
   different account and confirm the investor portfolio is not visible; ADMIN
   status does not bypass portfolio ownership.

The demo fixture contains only historical synthetic observations. A missing or
stale price must produce an incomplete valuation rather than a fabricated
current value.

## Technical-analysis walkthrough

1. Open a synthetic stock detail page and keep the `Synthetic` and `Historical`
   provenance labels visible.
2. Switch between `1D`, `1W`, `1M`, `1Y`, and `ALL`; compare line and
   candlestick views and toggle volume, SMA, EMA, Bollinger Bands, RSI, and
   MACD.
3. Explain that the committed fixture contains 120 weekday sessions per
   fictional instrument (720 prices and 120 snapshots) and that indicators
   intentionally show warm-up messages when the selected range is too short.
4. The fixture SHA-256 is
   `89abb74a6b45ffda12878eb0d12b7bcb99f64135fd02ef84ff0ac286960f4698`.
   It is validated by the repository tests and must never be described as
   genuine NEPSE data.

## Interview questions to rehearse

- **Why a provider interface?** It keeps React and API contracts independent of
  a licensed market-data source and makes replay fixtures testable.
- **How is portfolio correctness protected?** Transactions are append-only,
  replayed in date/sequence order with Decimal values, and guarded by
  owner-scoped authorization plus concurrency-safe writes.
- **Why is the portfolio valuation incomplete?** The latest observation is
  historical/stale, so the holding-level historical difference (NPR 11) is
  visible while aggregate market and unrealized totals remain unavailable
  instead of being presented as live data.
- **How is synthetic data made safe?** The fixture is deterministic, validated
  against OHLCV constraints, tied to a versioned SHA-256 manifest, and labelled
  in the UI.
- **What is intentionally out of scope?** Live NEPSE publication, brokerage
  integration, deployment, and cloud infrastructure.

## Resume evidence

- FastAPI + React market-research workspace with PostgreSQL identity/RBAC,
  owner-scoped watchlists, a historical screener, and technical indicators.
- Immutable Decimal portfolio ledger with weighted-average cost, fees-aware
  realized P&L, deterministic replay, and concurrency protection.
- Reproducible synthetic-data pipeline with provenance manifests, SHA-256
  verification, idempotent ingestion, and five-job CI quality gates.

## Troubleshooting

- If database authentication fails, verify that `backend/.env.demo.local` is
  present, ignored by Git, and targets `marketmitra_demo` with
  `marketmitra_demo_user`.
- If port 8000 is occupied, choose another backend port and use the same port in
  `VITE_API_BASE_URL`.
- If auth fails only on `localhost`, use matching `127.0.0.1` URLs for both
  frontend and API.
- If a demo login is unavailable, confirm the Windows Credential Manager entry
  `MarketMitra/demo-investor` or `MarketMitra/demo-admin` exists. Do not reset a
  password or create a replacement account during an interview startup.
- Check PostgreSQL with `pg_isready -h localhost -p 5432`. Do not run migrations
  or reset scripts against the existing `marketmitra` database or the demo
  database during a normal startup.
