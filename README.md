# MarketMitra

MarketMitra is a planned full-stack market analytics platform for the Nepal Stock Exchange (NEPSE). It will help users explore market performance, discover stocks, and review historical price information.

## Planned features

- Market overview dashboard
- Top gainers, top losers, and most active stocks
- Stock search and stock-detail pages
- Historical price charts
- Market analytics
- Later: user accounts, watchlists, price alerts, and notifications

## Tech stack

- Frontend: React, Vite, TypeScript, Tailwind CSS
- Backend: Python, FastAPI, SQLAlchemy, Pydantic
- Database: PostgreSQL, introduced after the initial MVP flow is validated

## High-level architecture

MarketMitra will use a modular monolith:

```text
React frontend -> FastAPI backend -> Market Data Provider
                                      |
                                      +-> Mock provider (initial MVP)
                                      +-> NEPSE provider (future)

FastAPI backend -> PostgreSQL repository (future)
```

The frontend communicates only with the backend. The backend owns API contracts, market-data normalization, provider selection, and eventual persistence. The first iteration uses mock market data and avoids external infrastructure such as Redis, WebSockets, microservices, and message brokers.

## Development status

Planning is complete. Application scaffolding, package installation, and implementation have not started.

See [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) for delivery phases and [docs/architecture.md](docs/architecture.md) for architectural guidance.
