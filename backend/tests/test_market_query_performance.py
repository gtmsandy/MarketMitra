"""SQLite query-count baselines for PostgreSQL-backed market provider paths.

Stock listing and search enforce the Milestone 7B constant-query budget. The
remaining mover tests intentionally describe current query growth; they are
diagnostic contracts, not endorsements of that N+1 behavior.
"""

from collections.abc import Callable
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import DailyPrice, Instrument, MarketSnapshot
from app.providers.postgres_market import PostgresMarketProvider
from tests.sql_measurement import measure_sql


ProviderCall = Callable[[PostgresMarketProvider], list]


def _make_market(instrument_count: int, change_percent: float) -> tuple[Engine, Session]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()

    instruments = [
        Instrument(
            symbol=f"SYM{index:03d}",
            company_name=f"Company {index:03d}",
            sector="Banking" if index % 2 == 0 else "Hydropower",
            security_type="EQUITY",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        for index in range(instrument_count)
    ]
    prices = [
        DailyPrice(
            symbol=instrument.symbol,
            date="2026-09-03",
            open=100.0,
            high=102.0,
            low=99.0,
            close=101.0,
            volume=1_000 + index,
            turnover=101_000.0 + index,
            change=change_percent,
            change_percent=change_percent,
            previous_close=100.0,
            is_ohlc_valid=True,
        )
        for index, instrument in enumerate(instruments)
    ]
    session.add_all(instruments + prices)
    session.add(
        MarketSnapshot(
            nepse_index=2_800.0,
            index_change=10.0,
            index_change_percent=0.36,
            turnover=1_000_000.0,
            total_volume=10_000,
            total_transactions=500,
            market_status="CLOSED",
            captured_at=datetime(2026, 9, 3, tzinfo=timezone.utc),
        )
    )
    session.commit()
    session.expunge_all()
    return engine, session


def _measure_provider_call(
    instrument_count: int,
    change_percent: float,
    call: ProviderCall,
) -> tuple[int, list]:
    engine, session = _make_market(instrument_count, change_percent)
    try:
        with measure_sql(engine) as measurement:
            result = call(PostgresMarketProvider(session))
        return measurement.statement_count, result
    finally:
        session.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("name", "change_percent", "call"),
    [
        ("stock list", 1.0, lambda provider: provider.get_stocks()),
        ("stock search", 1.0, lambda provider: provider.search_stocks("Company")),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_stock_query_count_is_constant(
    name: str,
    change_percent: float,
    call: ProviderCall,
) -> None:
    measurements = [
        _measure_provider_call(size, change_percent, call)
        for size in (2, 5, 20)
    ]

    assert [len(result) for _, result in measurements] == [2, 5, 20], name
    assert {count for count, _ in measurements} == {2}, name


@pytest.mark.parametrize(
    ("name", "change_percent", "call"),
    [
        ("gainers", 1.0, lambda provider: provider.get_top_gainers()),
        ("losers", -1.0, lambda provider: provider.get_top_losers()),
        ("most active", 1.0, lambda provider: provider.get_most_active()),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_market_mover_query_counts_grow_with_instrument_count(
    name: str,
    change_percent: float,
    call: ProviderCall,
) -> None:
    small_count, small_result = _measure_provider_call(2, change_percent, call)
    large_count, large_result = _measure_provider_call(5, change_percent, call)

    assert len(small_result) == 2, name
    assert len(large_result) == 5, name
    assert large_count - small_count == 3, name


def test_measurement_listener_is_detached_after_context_exit() -> None:
    engine, session = _make_market(1, 1.0)
    try:
        with measure_sql(engine) as first:
            session.query(Instrument).all()

        session.query(Instrument).all()

        with measure_sql(engine) as second:
            session.query(Instrument).all()

        assert first.statement_count == 1
        assert second.statement_count == 1
    finally:
        session.close()
        engine.dispose()
