# MarketMitra Development Roadmap

## Guiding priorities

1. Validate the frontend-to-backend product flow.
2. Keep market-data access replaceable through a provider abstraction.
3. Add persistence only after the MVP has proven its API and UI needs.
4. Defer user-specific and operational infrastructure until the public market experience is solid.

## Phase 0 — Planning foundation

- Establish architecture, scope controls, and development conventions.
- Define initial domain terminology and public API boundaries.
- Confirm that the first provider is mock data only.

**Milestone:** planning documentation is in place.

## Phase 1 — Mock-data MVP

- Initialize the React/Vite/TypeScript frontend and FastAPI backend when implementation is authorized.
- Implement a Mock Market Data Provider with stable, realistic sample market data.
- Build backend endpoints for market overview, ranked stocks, search, stock details, and historical prices.
- Build dashboard, search, stock-detail, and basic historical-chart user flows.
- Add tests for critical calculations, API contracts, and mock-provider behavior.

**Definition of MVP:** a user can open the dashboard, see a mock market overview and rankings, search a stock, open its detail page, and view its mock historical price chart through the backend API.

**Milestone:** a complete public, read-only frontend-to-backend flow works locally without a database or real NEPSE data.

## Phase 2 — Persistence and data-quality foundation

- Introduce PostgreSQL and migrations.
- Add repository interfaces and PostgreSQL implementations while preserving existing API contracts.
- Persist instruments, market snapshots, and historical price records.
- Add data validation, timestamps, and basic ingestion-status visibility.

**Milestone:** the application reads market views from persisted data without changing the frontend experience.

## Phase 3 — Real NEPSE data integration

- Implement a real NEPSE provider behind the existing provider abstraction.
- Normalize source data into the domain model.
- Add scheduled refresh behavior appropriate to the confirmed source and market schedule.
- Monitor source failures and surface data freshness.

**Milestone:** live or regularly refreshed NEPSE data can replace mock data without frontend changes.

## Phase 4 — Analytics expansion

- Add sector summaries, returns, trend indicators, and volume analysis.
- Improve filtering, pagination, and chart interactions based on demonstrated needs.
- Add targeted caching or precomputed aggregates only when measurement supports them.

**Milestone:** useful analysis beyond basic market listings and price history.

## Phase 5 — Accounts and alerts

- Add authentication and personalized watchlists.
- Add price-alert rules, durable evaluation records, and one notification channel.
- Introduce background processing only when alerts require it.

**Milestone:** users can save stocks and reliably receive configured alerts.

## Deferred by default

- Redis and distributed caches
- WebSockets or real-time streaming
- Microservices and message brokers
- Multiple notification providers
- AI trading recommendations
- Native mobile applications
