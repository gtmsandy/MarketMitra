"""Unit tests for live trading rules: ±15% stock limits, ±5% pre-open, and index circuit breakers."""

import pytest
from app.ingestion.live_validator import (
    IndexCircuitStatus,
    validate_index_circuit_breaker,
    validate_live_stock_quote,
)


class TestLiveStockQuoteValidation:
    def test_normal_session_within_15_percent_accepted(self) -> None:
        """Normal trading session accepts price movement within ±15%."""
        res_plus = validate_live_stock_quote("NABIL", ltp=115.0, previous_close=100.0)
        assert res_plus.is_valid is True
        assert res_plus.action == "ACCEPT"
        assert res_plus.calculated_change_percent == 15.0

        res_minus = validate_live_stock_quote("NABIL", ltp=85.0, previous_close=100.0)
        assert res_minus.is_valid is True
        assert res_minus.action == "ACCEPT"
        assert res_minus.calculated_change_percent == -15.0

        res_zero = validate_live_stock_quote("NABIL", ltp=100.0, previous_close=100.0)
        assert res_zero.is_valid is True
        assert res_zero.calculated_change_percent == 0.0

    def test_normal_session_exceeding_15_percent_rejected(self) -> None:
        """Normal trading session rejects price movement exceeding ±15% without clamping."""
        res_high = validate_live_stock_quote("NABIL", ltp=116.0, previous_close=100.0)
        assert res_high.is_valid is False
        assert res_high.action == "REJECT"
        assert res_high.calculated_change_percent == 16.0  # value is not clamped!

        res_low = validate_live_stock_quote("NABIL", ltp=84.0, previous_close=100.0)
        assert res_low.is_valid is False
        assert res_low.action == "REJECT"
        assert res_low.calculated_change_percent == -16.0  # value is not clamped!

    def test_pre_open_session_within_5_percent_accepted(self) -> None:
        """Pre-open order-entry session accepts price movement within ±5%."""
        res_plus = validate_live_stock_quote("NABIL", ltp=105.0, previous_close=100.0, is_pre_open=True)
        assert res_plus.is_valid is True
        assert res_plus.action == "ACCEPT"

        res_minus = validate_live_stock_quote("NABIL", ltp=95.0, previous_close=100.0, is_pre_open=True)
        assert res_minus.is_valid is True
        assert res_minus.action == "ACCEPT"

    def test_pre_open_session_exceeding_5_percent_rejected(self) -> None:
        """Pre-open session rejects movements > ±5%."""
        res_high = validate_live_stock_quote("NABIL", ltp=106.0, previous_close=100.0, is_pre_open=True)
        assert res_high.is_valid is False
        assert res_high.action == "REJECT"

        res_low = validate_live_stock_quote("NABIL", ltp=94.0, previous_close=100.0, is_pre_open=True)
        assert res_low.is_valid is False
        assert res_low.action == "REJECT"

    def test_corporate_action_day_flagged_not_clamped(self) -> None:
        """Confirmed corporate actions exceeding 15% are flagged for audit without value alteration."""
        res = validate_live_stock_quote(
            "NABIL", ltp=150.0, previous_close=100.0, is_corporate_action_day=True
        )
        assert res.is_valid is True
        assert res.action == "FLAG_CORPORATE_ACTION"
        assert res.calculated_change_percent == 50.0

    def test_nonpositive_prices_rejected(self) -> None:
        """Zero or negative LTP or previous_close is rejected."""
        res1 = validate_live_stock_quote("NABIL", ltp=0.0, previous_close=100.0)
        assert res1.is_valid is False
        assert res1.action == "REJECT"

        res2 = validate_live_stock_quote("NABIL", ltp=100.0, previous_close=-5.0)
        assert res2.is_valid is False
        assert res2.action == "REJECT"


class TestIndexCircuitBreakerValidation:
    def test_level_1_circuit_breaker_first_two_hours(self) -> None:
        """Index movement >= 5% in first 2 hours triggers 15-minute halt."""
        status_pos, msg_pos = validate_index_circuit_breaker(index_change_percent=5.1, session_minutes=45)
        assert status_pos == IndexCircuitStatus.LEVEL_1_HALT_15M

        status_neg, msg_neg = validate_index_circuit_breaker(index_change_percent=-5.0, session_minutes=110)
        assert status_neg == IndexCircuitStatus.LEVEL_1_HALT_15M

    def test_level_1_not_triggered_after_two_hours_unless_level_2(self) -> None:
        """5% move after 2 hours does not trigger Level 1; remains normal unless 8% hit."""
        status, msg = validate_index_circuit_breaker(index_change_percent=5.5, session_minutes=150)
        assert status == IndexCircuitStatus.NORMAL

    def test_level_2_full_day_suspension_at_8_percent(self) -> None:
        """Index movement >= 8% at any time triggers full-day trading suspension."""
        status1, _ = validate_index_circuit_breaker(index_change_percent=8.0, session_minutes=30)
        assert status1 == IndexCircuitStatus.LEVEL_2_HALT_DAY

        status2, _ = validate_index_circuit_breaker(index_change_percent=-8.5, session_minutes=180)
        assert status2 == IndexCircuitStatus.LEVEL_2_HALT_DAY

    def test_index_is_strictly_not_subject_to_stock_15_percent_limit(self) -> None:
        """Index circuit breaker uses 5%/8% rules and never applies the stock-level 15% rule."""
        status, _ = validate_index_circuit_breaker(index_change_percent=8.2, session_minutes=60)
        assert status == IndexCircuitStatus.LEVEL_2_HALT_DAY
