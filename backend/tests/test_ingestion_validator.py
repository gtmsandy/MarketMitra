"""Unit tests for IngestionValidator — no database required."""

from datetime import datetime, timedelta, timezone

import pytest

from app.ingestion.models import RawPriceRecord, RawSnapshotRecord
from app.ingestion.validator import IngestionValidator


def _valid_price(**overrides) -> RawPriceRecord:
    """Return a valid RawPriceRecord, optionally overriding fields."""
    base = RawPriceRecord(
        symbol="NABIL",
        date="2026-09-01",   # Monday — valid NEPSE trading day
        open=500.0,
        high=520.0,
        low=498.0,
        close=515.0,
        volume=100_000,
        turnover=51_500_000.0,
        change=13.0,
        change_percent=2.59,
        previous_close=502.0,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _valid_snapshot(**overrides) -> RawSnapshotRecord:
    base = RawSnapshotRecord(
        nepse_index=2786.42,
        index_change=21.35,
        index_change_percent=0.77,
        turnover=552_907_933.0,
        total_volume=1_241_890,
        total_transactions=38_640,
        market_status="Open",
        captured_at=datetime(2026, 9, 1, 11, 30, tzinfo=timezone.utc),
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


@pytest.fixture()
def validator() -> IngestionValidator:
    return IngestionValidator()


# ---------------------------------------------------------------------------
# Price validation — happy path
# ---------------------------------------------------------------------------

class TestPriceValidationValid:
    def test_valid_record_passes(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price()])
        assert len(result.valid) == 1
        assert len(result.rejected) == 0

    def test_mixed_batch_splits_correctly(self, validator: IngestionValidator) -> None:
        records = [
            _valid_price(symbol="NABIL"),
            _valid_price(symbol="NTC", date="2026-09-02"),
            _valid_price(high=400.0, close=450.0),   # high < close → rejected
        ]
        result = validator.validate_prices(records)
        assert len(result.valid) == 2
        assert len(result.rejected) == 1


# ---------------------------------------------------------------------------
# Symbol validation
# ---------------------------------------------------------------------------

class TestSymbolValidation:
    def test_empty_symbol_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(symbol="")])
        assert len(result.rejected) == 1
        rules = [e.rule for e in result.rejected[0][1]]
        assert "symbol_nonempty" in rules

    def test_symbol_too_long_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(symbol="ABCDEFGHIJK")])  # 11 chars
        assert len(result.rejected) == 1

    def test_lowercase_symbol_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(symbol="nabil")])
        assert len(result.rejected) == 1


# ---------------------------------------------------------------------------
# Date validation
# ---------------------------------------------------------------------------

class TestDateValidation:
    def test_malformed_date_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(date="03-09-2026")])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "date_format" in rules

    def test_invalid_calendar_date_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(date="2026-02-30")])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "date_format" in rules

    def test_future_date_rejected(self, validator: IngestionValidator) -> None:
        future = (datetime.now(tz=timezone.utc) + timedelta(days=5)).strftime("%Y-%m-%d")
        result = validator.validate_prices([_valid_price(date=future)])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "date_not_future" in rules

    def test_friday_rejected(self, validator: IngestionValidator) -> None:
        # 2026-09-04 is a Friday
        result = validator.validate_prices([_valid_price(date="2026-09-04")])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "date_not_weekend" in rules

    def test_saturday_rejected(self, validator: IngestionValidator) -> None:
        # 2026-09-05 is a Saturday
        result = validator.validate_prices([_valid_price(date="2026-09-05")])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "date_not_weekend" in rules

    def test_sunday_accepted(self, validator: IngestionValidator) -> None:
        # 2026-08-30 is a Sunday — valid NEPSE trading day
        result = validator.validate_prices([_valid_price(date="2026-08-30")])
        assert len(result.valid) == 1


# ---------------------------------------------------------------------------
# OHLC validation
# ---------------------------------------------------------------------------

class TestOHLCValidation:
    def test_high_less_than_low_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(high=490.0, low=510.0)])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "ohlc_consistency" in rules

    def test_high_less_than_open_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(open=530.0, high=520.0)])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "ohlc_consistency" in rules

    def test_high_less_than_close_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(high=510.0, close=520.0)])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "ohlc_consistency" in rules

    def test_low_greater_than_open_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(low=510.0, open=490.0)])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "ohlc_consistency" in rules

    def test_low_greater_than_close_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(low=520.0, close=510.0)])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "ohlc_consistency" in rules


# ---------------------------------------------------------------------------
# Price positivity
# ---------------------------------------------------------------------------

class TestPricePositivity:
    @pytest.mark.parametrize("field", ["open", "high", "low", "close"])
    def test_zero_price_rejected(self, validator: IngestionValidator, field: str) -> None:
        result = validator.validate_prices([_valid_price(**{field: 0.0})])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "price_positive" in rules

    @pytest.mark.parametrize("field", ["open", "high", "low", "close"])
    def test_negative_price_rejected(self, validator: IngestionValidator, field: str) -> None:
        result = validator.validate_prices([_valid_price(**{field: -1.0})])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "price_positive" in rules


# ---------------------------------------------------------------------------
# Volume and turnover
# ---------------------------------------------------------------------------

class TestVolumeAndTurnover:
    def test_negative_volume_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(volume=-1)])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "volume_nonnegative" in rules

    def test_zero_volume_accepted(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(volume=0)])
        assert len(result.valid) == 1

    def test_negative_turnover_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(turnover=-1.0)])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "turnover_nonnegative" in rules


# ---------------------------------------------------------------------------
# Change percent range
# ---------------------------------------------------------------------------

class TestChangePercentRange:
    def test_extreme_positive_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(change_percent=1001.0)])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "change_percent_range" in rules

    def test_below_minus_100_rejected(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(change_percent=-100.5)])
        rules = [e.rule for e in result.rejected[0][1]]
        assert "change_percent_range" in rules

    def test_boundary_values_accepted(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(change_percent=999.9)])
        assert len(result.valid) == 1


# ---------------------------------------------------------------------------
# Snapshot validation
# ---------------------------------------------------------------------------

class TestSnapshotValidation:
    def test_valid_snapshot_passes(self, validator: IngestionValidator) -> None:
        errors = validator.validate_snapshot(_valid_snapshot())
        assert errors == []

    def test_zero_index_rejected(self, validator: IngestionValidator) -> None:
        errors = validator.validate_snapshot(_valid_snapshot(nepse_index=0.0))
        rules = [e.rule for e in errors]
        assert "snapshot_index_positive" in rules

    def test_negative_turnover_rejected(self, validator: IngestionValidator) -> None:
        errors = validator.validate_snapshot(_valid_snapshot(turnover=-1.0))
        rules = [e.rule for e in errors]
        assert "snapshot_turnover_nonnegative" in rules

    def test_empty_status_rejected(self, validator: IngestionValidator) -> None:
        errors = validator.validate_snapshot(_valid_snapshot(market_status=""))
        rules = [e.rule for e in errors]
        assert "snapshot_status_nonempty" in rules
