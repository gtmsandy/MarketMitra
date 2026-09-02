# MarketMitra AI Development Instructions

## Project direction

MarketMitra is a NEPSE market analytics platform. The initial product validates a frontend-to-backend flow with a **Mock Market Data Provider**. Real NEPSE integration and PostgreSQL persistence are deferred until that MVP works.

## Architecture rules

- Build a modular monolith: one React frontend, one FastAPI backend, and clearly separated internal modules.
- Keep the frontend independent of data-provider details. It must use backend APIs only.
- Place market-data access behind a provider interface. Mock data is the initial provider; a real NEPSE provider must be swappable later without changing API consumers.
- Begin with in-memory/mock data. Introduce PostgreSQL behind repository interfaces only after the frontend-to-backend flow is validated.
- Keep domain concepts explicit: market overview, instruments, rankings, price history, and analytics.
- Avoid Redis, WebSockets, microservices, message brokers, and background-worker infrastructure until a demonstrated requirement exists.

## Coding conventions

- Use TypeScript for frontend code and Python type hints for backend code.
- Prefer small, cohesive modules with clear names and one responsibility.
- Keep API request/response models explicit and versionable.
- Use consistent formatting and linting tools once the applications are initialized; do not add tools without a clear need.
- Do not expose provider-specific payloads directly through backend endpoints.
- Favor simple, readable implementations over premature abstractions.

## AI agent workflow

1. Read the relevant planning and architecture documents before making a change.
2. Inspect the affected area and identify the smallest change that satisfies the request.
3. State assumptions when they materially affect behavior or architecture.
4. Implement only the requested scope; preserve unrelated user changes.
5. Add or update tests for critical business logic, API contracts, calculations, and provider behavior.
6. Run relevant checks when tooling exists, then report changed files and verification results.

## Scope and dependency controls

- Keep each change focused; do not combine refactors, feature work, and infrastructure changes without explicit approval.
- Add dependencies only when the standard library or existing project dependencies cannot reasonably satisfy the need.
- Before adding a dependency, document its purpose and confirm it does not introduce unnecessary infrastructure or vendor coupling.
- Do not add authentication, alerts, notifications, persistence, or real data ingestion during the mock-data MVP unless explicitly requested.
