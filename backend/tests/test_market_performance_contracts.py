"""Correctness contracts that must survive future query optimizations."""

from datetime import datetime, timezone

from app.db.models import DailyPrice, Instrument
from app.providers.postgres_market import PostgresMarketProvider
from tests.test_market_query_performance import _make_market


def test_stock_search_normalizes_whitespace_case_and_partial_company_name() -> None:
    engine, session = _make_market(12, 1.0)
    try:
        results = PostgresMarketProvider(session).search_stocks("  cOmPaNy 00  ")

        assert [row.symbol for row in results] == [
            "SYM000", "SYM001", "SYM002", "SYM003", "SYM004",
            "SYM005", "SYM006", "SYM007", "SYM008", "SYM009",
        ]
    finally:
        session.close()
        engine.dispose()


def test_market_mover_ties_have_stable_turnover_then_symbol_order() -> None:
    engine, session = _make_market(5, 1.0)
    try:
        provider = PostgresMarketProvider(session)
        expected = ["SYM004", "SYM003", "SYM002", "SYM001", "SYM000"]

        assert [row.symbol for row in provider.get_top_gainers()] == expected
        assert [row.symbol for row in provider.get_most_active()] == expected
    finally:
        session.close()
        engine.dispose()


def test_rankings_use_latest_valid_common_equity_session() -> None:
    engine, session = _make_market(2, 1.0)
    try:
        session.add_all(
            [
                Instrument(
                    symbol="MISSING", company_name="Missing Observation",
                    sector="Banking", security_type="EQUITY",
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                Instrument(
                    symbol="FUND001", company_name="Non-equity Fund",
                    sector="Mutual Fund", security_type="MUTUAL_FUND",
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                DailyPrice(
                    symbol="SYM000", date="2026-09-04", open=100.0,
                    high=102.0, low=99.0, close=101.0, volume=1_000,
                    turnover=101_000.0, change=1.0, change_percent=1.0,
                    previous_close=100.0, is_ohlc_valid=False,
                    validation_reason="ohlc_ordering",
                ),
                DailyPrice(
                    symbol="FUND001", date="2026-09-05", open=100.0,
                    high=102.0, low=99.0, close=101.0, volume=1_000,
                    turnover=101_000.0, change=1.0, change_percent=1.0,
                    previous_close=100.0, is_ohlc_valid=True,
                ),
            ]
        )
        session.commit()
        session.expunge_all()

        rows = PostgresMarketProvider(session).get_top_gainers()

        assert [row.symbol for row in rows] == ["SYM001", "SYM000"]
        assert {row.observation_date for row in rows} == {"2026-09-03"}
    finally:
        session.close()
        engine.dispose()
