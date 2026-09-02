"""Integration tests for PostgresMarketProvider against SQLite in-memory.

These tests prove that data persisted through the repository layer is
correctly translated into the existing MarketDataProvider domain contract
without requiring a live PostgreSQL instance.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base import Base
from app.providers.postgres_market import PostgresMarketProvider
from app.providers.mock_market import MockMarketProvider
from app.repositories.instrument_repository import PostgresInstrumentRepository
from app.repositories.market_repository import PostgresMarketSnapshotRepository
from app.repositories.price_repository import DailyPriceRow, PostgresDailyPriceRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def seeded_session(session: Session) -> Session:
    """Populate SQLite in-memory with all MockMarketProvider data, then return
    the session ready for PostgresMarketProvider queries."""
    mock = MockMarketProvider()
    instruments_repo = PostgresInstrumentRepository(session)
    snapshots_repo = PostgresMarketSnapshotRepository(session)
    prices_repo = PostgresDailyPriceRepository(session)

    # Instruments
    stocks = mock.get_stocks()
    for stock in stocks:
        instruments_repo.upsert(stock.symbol, stock.company_name)
    session.flush()

    # Market snapshot
    overview = mock.get_market_overview()
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

    # Daily prices for every instrument
    for stock in stocks:
        history = mock.get_stock_history(stock.symbol) or []
        rows = []
        for i, point in enumerate(history):
            previous_close = history[i - 1].close if i > 0 else point.open
            change = round(point.close - previous_close, 4)
            change_pct = round((change / previous_close) * 100, 4) if previous_close else 0.0
            rows.append(DailyPriceRow(
                symbol=stock.symbol,
                date=point.date,
                open=point.open,
                high=point.high,
                low=point.low,
                close=point.close,
                volume=point.volume,
                turnover=round(point.close * point.volume, 2),
                change=change,
                change_percent=change_pct,
                previous_close=previous_close,
            ))
        prices_repo.upsert_many(rows)

    session.commit()
    return session


# ---------------------------------------------------------------------------
# PostgresMarketProvider integration tests
# ---------------------------------------------------------------------------

class TestPostgresMarketProviderOverview:
    def test_get_market_overview_returns_domain_model(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        overview = provider.get_market_overview()

        assert overview.nepse_index == 2_786.42
        assert overview.market_status == "Open"
        assert overview.total_transactions == 38_640
        assert overview.turnover > 0
        assert isinstance(overview.last_updated, datetime)

    def test_get_market_overview_no_data_raises(self, session: Session) -> None:
        """Provider must raise clearly when no snapshot exists."""
        provider = PostgresMarketProvider(session)
        with pytest.raises(RuntimeError, match="No market snapshot found"):
            provider.get_market_overview()


class TestPostgresMarketProviderGainersLosers:
    def test_gainers_all_positive(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        gainers = provider.get_top_gainers()
        assert len(gainers) > 0
        for g in gainers:
            assert g.change_percent > 0, f"{g.symbol} has non-positive change_percent"

    def test_gainers_sorted_descending(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        gainers = provider.get_top_gainers()
        percents = [g.change_percent for g in gainers]
        assert percents == sorted(percents, reverse=True)

    def test_losers_all_negative(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        losers = provider.get_top_losers()
        assert len(losers) > 0
        for l in losers:
            assert l.change_percent < 0, f"{l.symbol} has non-negative change_percent"

    def test_losers_sorted_ascending(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        losers = provider.get_top_losers()
        percents = [l.change_percent for l in losers]
        assert percents == sorted(percents)


class TestPostgresMarketProviderMostActive:
    def test_most_active_sorted_by_turnover(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        active = provider.get_most_active()
        assert len(active) > 0
        turnovers = [a.turnover for a in active]
        assert turnovers == sorted(turnovers, reverse=True)

    def test_most_active_shape(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        for item in provider.get_most_active():
            assert item.symbol
            assert item.company_name
            assert item.ltp > 0
            assert item.volume > 0
            assert item.turnover > 0


class TestPostgresMarketProviderStocks:
    def test_get_stocks_returns_all_instruments(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        stocks = provider.get_stocks()
        assert len(stocks) == 8  # matches MockMarketProvider fixture count

    def test_get_stocks_shape(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        for stock in provider.get_stocks():
            assert stock.symbol
            assert stock.company_name
            assert stock.ltp > 0

    def test_search_stocks_by_symbol(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        results = provider.search_stocks("NAB")
        symbols = [r.symbol for r in results]
        assert "NABIL" in symbols

    def test_search_stocks_no_match(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        assert provider.search_stocks("ZZZZZ") == []


class TestPostgresMarketProviderStockDetail:
    def test_known_symbol_returns_detail(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        detail = provider.get_stock_detail("NABIL")
        assert detail is not None
        assert detail.symbol == "NABIL"
        assert detail.company_name == "Nabil Bank Limited"
        assert detail.ltp > 0
        assert detail.fifty_two_week_high >= detail.fifty_two_week_low
        assert detail.fifty_two_week_high > 0

    def test_case_insensitive_lookup(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        detail = provider.get_stock_detail("nabil")
        assert detail is not None
        assert detail.symbol == "NABIL"

    def test_unknown_symbol_returns_none(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        assert provider.get_stock_detail("NONEXIST") is None


class TestPostgresMarketProviderHistory:
    def test_returns_history(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        history = provider.get_stock_history("NABIL")
        assert history is not None
        assert len(history) == 180

    def test_history_chronological(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        history = provider.get_stock_history("NABIL")
        assert history is not None
        dates = [p.date for p in history]
        assert dates == sorted(dates)

    def test_history_ohlc_consistent(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        history = provider.get_stock_history("NABIL")
        assert history is not None
        for point in history:
            assert point.high >= point.low
            assert point.high >= point.open
            assert point.high >= point.close
            assert point.low <= point.open
            assert point.low <= point.close

    def test_history_shape(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        history = provider.get_stock_history("NABIL")
        assert history is not None
        for point in history:
            assert point.date
            assert point.open > 0
            assert point.volume > 0

    def test_unknown_symbol_returns_none(self, seeded_session: Session) -> None:
        provider = PostgresMarketProvider(seeded_session)
        assert provider.get_stock_history("NONEXIST") is None
