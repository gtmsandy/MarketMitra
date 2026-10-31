"""Correctness contracts that must survive future query optimizations."""

from datetime import datetime, timezone

import pytest

from app.db.models import DailyPrice, Instrument
from app.providers.postgres_market import PostgresMarketProvider
from tests.test_market_query_performance import _make_market
from tests.sql_measurement import measure_sql


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


def test_stock_search_treats_sql_wildcards_as_literal_characters() -> None:
    engine, session = _make_market(1, 1.0)
    try:
        session.add_all(
            [
                Instrument(
                    symbol="PCT%01", company_name="Percent Company",
                    sector="Banking", security_type="EQUITY",
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                Instrument(
                    symbol="UNDER_01", company_name="Underscore Company",
                    sector="Banking", security_type="EQUITY",
                    created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ),
                DailyPrice(
                    symbol="PCT%01", date="2026-09-03", open=100.0,
                    high=102.0, low=99.0, close=101.0, volume=1_000,
                    turnover=101_000.0, change=1.0, change_percent=1.0,
                    previous_close=100.0, is_ohlc_valid=True,
                ),
                DailyPrice(
                    symbol="UNDER_01", date="2026-09-03", open=100.0,
                    high=102.0, low=99.0, close=101.0, volume=1_000,
                    turnover=101_000.0, change=1.0, change_percent=1.0,
                    previous_close=100.0, is_ohlc_valid=True,
                ),
            ]
        )
        session.commit()
        provider = PostgresMarketProvider(session)

        assert [row.symbol for row in provider.search_stocks("%")] == ["PCT%01"]
        assert [row.symbol for row in provider.search_stocks("_")] == ["UNDER_01"]
    finally:
        session.close()
        engine.dispose()


def test_stock_list_preserves_universe_and_latest_valid_per_symbol() -> None:
    engine, session = _make_market(1, 1.0)
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
                    symbol="FUND001", date="2026-09-02", open=100.0,
                    high=102.0, low=99.0, close=101.0, volume=1_000,
                    turnover=101_000.0, change=1.0, change_percent=1.0,
                    previous_close=100.0, is_ohlc_valid=True,
                ),
                DailyPrice(
                    symbol="SYM000", date="2026-09-04", open=100.0,
                    high=90.0, low=99.0, close=101.0, volume=1_000,
                    turnover=101_000.0, change=1.0, change_percent=1.0,
                    previous_close=100.0, is_ohlc_valid=False,
                    validation_reason="ohlc_ordering",
                ),
            ]
        )
        session.commit()

        rows = PostgresMarketProvider(session).get_stocks()

        assert [row.symbol for row in rows] == ["FUND001", "SYM000"]
        assert [row.stock_observation_date for row in rows] == [
            "2026-09-02", "2026-09-03"
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


def test_loser_ties_have_stable_turnover_then_symbol_order() -> None:
    engine, session = _make_market(5, -1.0)
    try:
        expected = ["SYM004", "SYM003", "SYM002", "SYM001", "SYM000"]

        assert [
            row.symbol for row in PostgresMarketProvider(session).get_top_losers()
        ] == expected
    finally:
        session.close()
        engine.dispose()


def test_market_movers_preserve_sign_rules_fields_and_turnover_ranking() -> None:
    engine, session = _make_market(3, 0.0)
    try:
        positive, negative, unchanged = session.query(DailyPrice).order_by(
            DailyPrice.symbol
        ).all()
        positive.close = 105.0
        positive.change = 5.0
        positive.change_percent = 5.0
        positive.volume = 1_500
        positive.turnover = 150_000.0
        negative.close = 95.0
        negative.change = -5.0
        negative.change_percent = -5.0
        negative.volume = 3_000
        negative.turnover = 300_000.0
        unchanged.close = 100.0
        unchanged.change = 0.0
        unchanged.change_percent = 0.0
        unchanged.volume = 2_000
        unchanged.turnover = 200_000.0
        session.commit()
        session.expunge_all()

        provider = PostgresMarketProvider(session)

        assert [row.model_dump() for row in provider.get_top_gainers()] == [{
            "symbol": "SYM000", "company_name": "Company 000", "ltp": 105.0,
            "change_percent": 5.0, "volume": 1_500,
            "observation_date": "2026-09-03",
        }]
        assert [row.model_dump() for row in provider.get_top_losers()] == [{
            "symbol": "SYM001", "company_name": "Company 001", "ltp": 95.0,
            "change_percent": -5.0, "volume": 3_000,
            "observation_date": "2026-09-03",
        }]
        assert [row.model_dump() for row in provider.get_most_active()] == [
            {
                "symbol": "SYM001", "company_name": "Company 001", "ltp": 95.0,
                "volume": 3_000, "turnover": 300_000.0,
                "observation_date": "2026-09-03",
            },
            {
                "symbol": "SYM002", "company_name": "Company 002", "ltp": 100.0,
                "volume": 2_000, "turnover": 200_000.0,
                "observation_date": "2026-09-03",
            },
            {
                "symbol": "SYM000", "company_name": "Company 000", "ltp": 105.0,
                "volume": 1_500, "turnover": 150_000.0,
                "observation_date": "2026-09-03",
            },
        ]
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


def test_stock_detail_fetches_only_its_inclusive_52_week_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, session = _make_market(1, 1.0)
    try:
        session.add_all(
            [
                DailyPrice(
                    symbol="SYM000", date="2025-09-03", open=100.0,
                    high=999.0, low=1.0, close=100.0, volume=1,
                    turnover=100.0, previous_close=100.0, is_ohlc_valid=True,
                ),
                DailyPrice(
                    symbol="SYM000", date="2025-09-04", open=100.0,
                    high=150.0, low=75.0, close=100.0, volume=2,
                    turnover=200.0, previous_close=100.0, is_ohlc_valid=True,
                ),
                DailyPrice(
                    symbol="SYM000", date="2026-01-01", open=100.0,
                    high=9_999.0, low=0.0, close=100.0, volume=3,
                    turnover=300.0, previous_close=100.0, is_ohlc_valid=False,
                    validation_reason="ohlc_ordering",
                ),
                DailyPrice(
                    symbol="SYM000", date="2026-09-04", open=100.0,
                    high=9_999.0, low=0.0, close=100.0, volume=4,
                    turnover=400.0, previous_close=100.0, is_ohlc_valid=False,
                    validation_reason="ohlc_ordering",
                ),
            ]
        )
        session.commit()
        session.expunge_all()
        provider = PostgresMarketProvider(session)
        range_query = provider._prices.get_by_symbol_and_date_range
        retrieval: dict[str, object] = {}

        def capture_range(
            symbol: str, start_date: str, end_date: str
        ) -> list[DailyPrice]:
            rows = range_query(symbol, start_date, end_date)
            retrieval.update(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                dates=[row.date for row in rows],
            )
            return rows

        def reject_unbounded_history(symbol: str) -> list[DailyPrice]:
            pytest.fail(f"unbounded history query used for {symbol}")

        monkeypatch.setattr(
            provider._prices, "get_by_symbol_and_date_range", capture_range
        )
        monkeypatch.setattr(
            provider._prices, "get_by_symbol", reject_unbounded_history
        )

        with measure_sql(engine) as measurement:
            detail = provider.get_stock_detail("sym000")

        assert detail is not None
        assert measurement.statement_count == 4
        assert retrieval == {
            "symbol": "SYM000",
            "start_date": "2025-09-04",
            "end_date": "2026-09-03",
            "dates": ["2025-09-04", "2026-09-03"],
        }
        assert detail.model_dump() == {
            "symbol": "SYM000",
            "company_name": "Company 000",
            "ltp": 101.0,
            "change": 1.0,
            "change_percent": 1.0,
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "previous_close": 100.0,
            "volume": 1_000,
            "last_updated": datetime(2026, 9, 3, tzinfo=timezone.utc),
            "fifty_two_week_high": 150.0,
            "fifty_two_week_low": 75.0,
            "stock_observation_date": "2026-09-03",
            "market_snapshot_date": datetime(2026, 9, 3),
        }
    finally:
        session.close()
        engine.dispose()


def test_stock_detail_with_one_or_no_valid_observation() -> None:
    engine, session = _make_market(1, 1.0)
    try:
        session.add(
            Instrument(
                symbol="MISSING", company_name="Missing Observation",
                sector="Banking", security_type="EQUITY",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        )
        session.commit()
        session.expunge_all()
        provider = PostgresMarketProvider(session)

        detail = provider.get_stock_detail("SYM000")

        assert detail is not None
        assert detail.fifty_two_week_high == 102.0
        assert detail.fifty_two_week_low == 99.0
        assert provider.get_stock_detail("MISSING") is None
    finally:
        session.close()
        engine.dispose()
