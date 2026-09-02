# MarketMitra Architecture

## Architectural style

MarketMitra will begin as a **modular monolith**. The project will have one frontend application and one backend application, with clearly separated modules inside the backend. This keeps local development and deployment simple while preserving boundaries that support later growth.

The initial system uses mock market data and no database. PostgreSQL and a real NEPSE provider are planned extensions, not prerequisites for validating the first user experience.

```text
Browser
  |
  v
React frontend
  |
  | HTTP API
  v
FastAPI backend
  |- API layer
  |- Domain/services layer
  |- Market data provider abstraction
  |- Mock Market Data Provider
  `- Repository abstraction (future)
       `- PostgreSQL implementation (future)
```

## Frontend and backend separation

The React frontend owns presentation, navigation, client-side interaction, and rendering of API responses. It must not fetch from a NEPSE source directly or contain provider-specific parsing logic.

The FastAPI backend owns stable public API contracts, request validation, response shaping, domain logic, market-data normalization, and provider selection. This boundary means the frontend can stay stable when mock data is replaced by real data or when persistence is introduced.

Initial backend endpoints should cover:

- Market overview
- Top gainers, losers, and most active stocks
- Stock search
- Stock detail
- Historical price data

## Provider abstraction

Market data is accessed through a provider interface defined around application needs rather than an external source's response format. A provider returns normalized domain data for overview metrics, stock rankings, instruments, stock details, and historical prices.

The first implementation is the Mock Market Data Provider. It should be deterministic enough for UI development and automated tests, while resembling realistic market data.

Later, a NEPSE provider can implement the same interface. Source-specific concerns—fetching, parsing, retries, mapping, and timestamps—remain inside that implementation. The API layer and frontend should not need to change merely because the provider changes.

## Future database integration

PostgreSQL is deliberately deferred until the mock-data MVP validates the user flows and API shape. When introduced, persistence should sit behind repository interfaces so domain services do not depend directly on SQLAlchemy queries.

The likely initial persisted entities are:

- Instruments and sectors
- Market snapshots
- Daily historical price bars
- Data-source and freshness metadata

Database integration must preserve existing public API contracts. Migrations, indexes, validation, and retention decisions should be introduced together with the first persistence use case—not speculatively.

## Explicitly deferred infrastructure

The initial architecture excludes Redis, WebSockets, microservices, message brokers, and distributed background workers. These components add operational complexity and should only be introduced after a concrete requirement—such as measured performance pressure, reliable live streaming, or alert processing—demands them.
