"""Seed PostgreSQL with deterministic mock market data.

Populates the three tables (instruments, market_snapshots, daily_prices)
using the existing MockMarketProvider as the authoritative data source.
The script is idempotent: re-running it updates instrument records and
skips daily_price rows that already exist (unique on symbol + date).

Usage (from the backend/ directory):
    .venv\\Scripts\\python -m app.scripts.seed_market_data

Requires DATABASE_URL to be set in the environment or in a .env file.
"""

import sys

from dotenv import load_dotenv
from sqlalchemy.orm import Session

load_dotenv()


def _build_session() -> Session:
    from app.core.config import get_database_url
    from app.db.base import make_session_factory

    factory = make_session_factory(get_database_url())
    return factory()


def seed(session: Session) -> None:
    """Populate the database from MockMarketProvider data.

    Safe to call multiple times; existing records are updated/skipped.
    """
    from app.db.base import Base, make_engine
    from app.core.config import get_database_url
    from app.providers.mock_market import MockMarketProvider
    from app.repositories.instrument_repository import PostgresInstrumentRepository
    from app.repositories.market_repository import PostgresMarketSnapshotRepository
    from app.repositories.price_repository import (
        DailyPriceRow,
        PostgresDailyPriceRepository,
    )

    # Ensure tables exist (no-op if already created by Alembic).
    engine = make_engine(get_database_url())
    Base.metadata.create_all(engine)

    provider = MockMarketProvider()
    instruments_repo = PostgresInstrumentRepository(session)
    snapshots_repo = PostgresMarketSnapshotRepository(session)
    prices_repo = PostgresDailyPriceRepository(session)

    # 1. Seed instruments from the stock listing.
    stocks = provider.get_stocks()
    for stock in stocks:
        instruments_repo.upsert(
            symbol=stock.symbol,
            company_name=stock.company_name,
        )
    session.flush()
    print(f"  Instruments: {len(stocks)} upserted.")

    # 2. Seed market snapshot from overview.
    overview = provider.get_market_overview()
    snapshots_repo.insert(
        nepse_index=overview.nepse_index,
        index_change=overview.index_change,
        index_change_percent=overview.index_change_percent,
        turnover=overview.turnover,
        total_volume=overview.total_volume,
        total_transactions=overview.total_transactions,
        market_status=overview.market_status,
        captured_at=overview.last_updated,
    )
    session.flush()
    print("  Market snapshot: 1 inserted.")

    # 3. Seed daily prices for each instrument.
    total_inserted = 0
    for stock in stocks:
        history = provider.get_stock_history(stock.symbol)
        if not history:
            continue

        rows: list[DailyPriceRow] = []
        prev_close = history[0].open  # bootstrap previous close
        for i, point in enumerate(history):
            close = point.close
            previous_close = history[i - 1].close if i > 0 else prev_close
            change = round(close - previous_close, 4)
            change_pct = round((change / previous_close) * 100, 4) if previous_close else 0.0

            # Approximate per-day turnover as close * volume.
            turnover = round(close * point.volume, 2)

            rows.append(DailyPriceRow(
                symbol=stock.symbol,
                date=point.date,
                open=point.open,
                high=point.high,
                low=point.low,
                close=close,
                volume=point.volume,
                turnover=turnover,
                change=change,
                change_percent=change_pct,
                previous_close=previous_close,
            ))

        inserted = prices_repo.upsert_many(rows)
        total_inserted += inserted

    session.commit()
    print(f"  Daily prices: {total_inserted} inserted.")
    print("Seed complete.")


def main() -> None:
    print("Seeding MarketMitra database from mock data…")
    session = _build_session()
    try:
        seed(session)
    except Exception as exc:
        session.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
