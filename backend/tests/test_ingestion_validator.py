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
# Validation mode compatibility
# ---------------------------------------------------------------------------

class TestValidationModeCompatibility:
    def test_default_mode_is_strict(self, validator: IngestionValidator) -> None:
        """validate_prices() without mode defaults to strict validation."""
        record = _valid_price(open=530.0, high=520.0, low=500.0, close=515.0)
        result_default = validator.validate_prices([record])
        result_strict = validator.validate_prices([record], mode="strict")

        assert len(result_default.rejected) == 1
        assert len(result_strict.rejected) == 1
        assert [e.rule for e in result_default.rejected[0][1]] == [
            e.rule for e in result_strict.rejected[0][1]
        ]

    def test_validate_prices_accepts_mode_as_keyword(self, validator: IngestionValidator) -> None:
        """Service calls validator.validate_prices(records, mode=...) as keyword argument."""
        record = _valid_price()
        result_strict = validator.validate_prices([record], mode="strict")
        result_historical = validator.validate_prices([record], mode="historical")
        assert len(result_strict.valid) == 1
        assert len(result_historical.valid) == 1

    def test_validate_prices_accepts_mode_as_positional(self, validator: IngestionValidator) -> None:
        """Positional mode argument is also supported."""
        record = _valid_price()
        result = validator.validate_prices([record], "strict")
        assert len(result.valid) == 1

    @pytest.mark.parametrize("bad_mode", ["unsupported", "", "HISTORICAL", "Strict", None, 123])
    def test_invalid_mode_raises_value_error(self, validator: IngestionValidator, bad_mode: object) -> None:
        """Unrecognized validation mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid validation mode"):
            validator.validate_prices([_valid_price()], mode=bad_mode)  # type: ignore[arg-type]

    def test_validate_price_record_directly_rejects_invalid_mode(
        self, validator: IngestionValidator
    ) -> None:
        """Internal _validate_price_record also rejects invalid mode."""
        from datetime import date
        with pytest.raises(ValueError, match="Invalid validation mode"):
            validator._validate_price_record(_valid_price(), date.today(), mode="invalid")  # type: ignore[arg-type]
    def test_mode_passed_to_per_record_validation(self, validator: IngestionValidator) -> None:
        """Historical mode still enforces canonical OHLC ordering."""
        record = _valid_price(open=530.0, high=520.0, low=500.0, close=515.0)
        res_strict = validator.validate_prices([record], mode="strict")
        res_historical = validator.validate_prices([record], mode="historical")
        assert len(res_strict.rejected) == 1
        assert len(res_historical.rejected) == 1

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

    def test_historical_accepts_underscore_symbols(self, validator: IngestionValidator) -> None:
        for sym in ["GBD80_81", "NICD83_84", "NMBD87_88", "GBILD84_85"]:
            res = validator.validate_prices([_valid_price(symbol=sym)], mode="historical")
            assert len(res.valid) == 1, f"Failed to accept {sym} in historical mode"

    def test_historical_accepts_12_character_symbol_nifraur85_86(
        self, validator: IngestionValidator
    ) -> None:
        res = validator.validate_prices([_valid_price(symbol="NIFRAUR85_86")], mode="historical")
        assert len(res.valid) == 1
        assert len(res.rejected) == 0

    def test_strict_rejects_underscore_symbols(self, validator: IngestionValidator) -> None:
        res = validator.validate_prices([_valid_price(symbol="GBD80_81")], mode="strict")
        assert len(res.rejected) == 1
        assert "symbol_nonempty" in [e.rule for e in res.rejected[0][1]]

    def test_strict_rejects_12_char_symbol(self, validator: IngestionValidator) -> None:
        res = validator.validate_prices([_valid_price(symbol="NIFRAUR85_86")], mode="strict")
        assert len(res.rejected) == 1
        assert "symbol_nonempty" in [e.rule for e in res.rejected[0][1]]

    def test_historical_rejects_symbols_longer_than_12_characters(
        self, validator: IngestionValidator
    ) -> None:
        res = validator.validate_prices([_valid_price(symbol="NIFRAUR85_86X")], mode="historical")
        assert len(res.rejected) == 1
        assert "symbol_nonempty" in [e.rule for e in res.rejected[0][1]]

    @pytest.mark.parametrize("bad_sym", ["adbl", "gbd80_81", "ADBL-D83", "ADBL.D83", "ADBL 83", " ADBL", "ADBL@1", ""])
    def test_invalid_symbol_characters_rejected_in_both_modes(
        self, validator: IngestionValidator, bad_sym: str
    ) -> None:
        res_strict = validator.validate_prices([_valid_price(symbol=bad_sym)], mode="strict")
        assert len(res_strict.rejected) == 1
        assert "symbol_nonempty" in [e.rule for e in res_strict.rejected[0][1]]

        res_hist = validator.validate_prices([_valid_price(symbol=bad_sym)], mode="historical")
        assert len(res_hist.rejected) == 1
        assert "symbol_nonempty" in [e.rule for e in res_hist.rejected[0][1]]

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

    def test_friday_accepted_in_historical_mode(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(date="2022-05-20")], mode="historical")
        assert len(result.valid) == 1

    def test_saturday_rejected_in_historical_mode(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(date="2022-05-21")], mode="historical")
        assert len(result.rejected) == 1
        assert "date_not_weekend" in [e.rule for e in result.rejected[0][1]]

# ---------------------------------------------------------------------------
# OHLC validation
# ---------------------------------------------------------------------------

class TestOHLCValidation:
    def test_strict_rejects_close_greater_than_high(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(high=510.0, close=520.0)], mode="strict")
        assert len(result.rejected) == 1
        assert "ohlc_consistency" in [e.rule for e in result.rejected[0][1]]

    def test_strict_rejects_close_less_than_low(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(low=510.0, close=500.0)], mode="strict")
        assert len(result.rejected) == 1
        assert "ohlc_consistency" in [e.rule for e in result.rejected[0][1]]

    def test_strict_rejects_open_greater_than_high(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(open=530.0, high=520.0)], mode="strict")
        assert len(result.rejected) == 1
        assert "ohlc_consistency" in [e.rule for e in result.rejected[0][1]]

    def test_strict_rejects_open_less_than_low(self, validator: IngestionValidator) -> None:
        result = validator.validate_prices([_valid_price(low=510.0, open=490.0)], mode="strict")
        assert len(result.rejected) == 1
        assert "ohlc_consistency" in [e.rule for e in result.rejected[0][1]]

    def test_historical_rejects_close_outside_range(self, validator: IngestionValidator) -> None:
        # close > high (e.g. ADBLD83 2025-04-07: open=1090, high=1090, low=1090, ltp/close=1111.70)
        res_above = validator.validate_prices(
            [_valid_price(open=1090.0, high=1090.0, low=1090.0, close=1111.70)], mode="historical"
        )
        assert len(res_above.rejected) == 1
        # close < low
        res_below = validator.validate_prices(
            [_valid_price(open=510.0, high=520.0, low=500.0, close=490.0)], mode="historical"
        )
        assert len(res_below.rejected) == 1

    def test_historical_rejects_open_outside_range(self, validator: IngestionValidator) -> None:
        # open > high
        res_above = validator.validate_prices(
            [_valid_price(open=530.0, high=520.0, low=500.0, close=515.0)], mode="historical"
        )
        assert len(res_above.rejected) == 1
        # open < low
        res_below = validator.validate_prices(
            [_valid_price(open=480.0, high=520.0, low=500.0, close=515.0)], mode="historical"
        )
        assert len(res_below.rejected) == 1

    def test_both_modes_reject_high_less_than_low(self, validator: IngestionValidator) -> None:
        res_strict = validator.validate_prices([_valid_price(high=490.0, low=510.0)], mode="strict")
        assert len(res_strict.rejected) == 1
        assert "ohlc_consistency" in [e.rule for e in res_strict.rejected[0][1]]

        res_historical = validator.validate_prices([_valid_price(high=490.0, low=510.0)], mode="historical")
        assert len(res_historical.rejected) == 1
        assert "ohlc_consistency" in [e.rule for e in res_historical.rejected[0][1]]

    def test_default_mode_rejects_close_outside_high_low(self, validator: IngestionValidator) -> None:
        # Default mode is strict
        result = validator.validate_prices([_valid_price(high=510.0, close=520.0)])
        assert len(result.rejected) == 1
        assert "ohlc_consistency" in [e.rule for e in result.rejected[0][1]]
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

    @pytest.mark.parametrize("field", ["open", "high", "low", "close"])
    def test_historical_mode_rejects_nonpositive_price(
        self, validator: IngestionValidator, field: str
    ) -> None:
        res_zero = validator.validate_prices([_valid_price(**{field: 0.0})], mode="historical")
        assert "price_positive" in [e.rule for e in res_zero.rejected[0][1]]

        res_neg = validator.validate_prices([_valid_price(**{field: -10.0})], mode="historical")
        assert "price_positive" in [e.rule for e in res_neg.rejected[0][1]]

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

    def test_historical_mode_accepts_fowadp_long_gap_change(self, validator: IngestionValidator) -> None:
        """FOWADP on 2022-05-11 traded at 1199 after 8 months at 80 (change=1398.75%). Accepted in historical."""
        rec = _valid_price(symbol="FOWADP", change_percent=1398.75)
        res_hist = validator.validate_prices([rec], mode="historical")
        assert len(res_hist.valid) == 1
        res_strict = validator.validate_prices([rec], mode="strict")
        assert len(res_strict.rejected) == 1
        assert "change_percent_range" in [e.rule for e in res_strict.rejected[0][1]]

    def test_historical_mode_accepts_nmfbsp_long_gap_change(self, validator: IngestionValidator) -> None:
        """NMFBSP on 2021-10-10 traded at 1537 after 3 months at 100 (change=1437.0%). Accepted in historical."""
        rec = _valid_price(symbol="NMFBSP", change_percent=1437.0)
        res_hist = validator.validate_prices([rec], mode="historical")
        assert len(res_hist.valid) == 1
        res_strict = validator.validate_prices([rec], mode="strict")
        assert len(res_strict.rejected) == 1
        assert "change_percent_range" in [e.rule for e in res_strict.rejected[0][1]]

    def test_historical_mode_accepts_wnlbp_long_gap_change(self, validator: IngestionValidator) -> None:
        """WNLBP on 2025-10-08 traded at 1138 after 3 months at 100 (change=1038.0%). Accepted in historical."""
        rec = _valid_price(symbol="WNLBP", change_percent=1038.0)
        res_hist = validator.validate_prices([rec], mode="historical")
        assert len(res_hist.valid) == 1
        res_strict = validator.validate_prices([rec], mode="strict")
        assert len(res_strict.rejected) == 1
        assert "change_percent_range" in [e.rule for e in res_strict.rejected[0][1]]

    def test_historical_mode_rejects_greater_than_2000_percent(
        self, validator: IngestionValidator
    ) -> None:
        """Truly absurd changes (>2000%) remain rejected even in historical mode."""
        rec = _valid_price(change_percent=2500.0)
        res = validator.validate_prices([rec], mode="historical")
        assert len(res.rejected) == 1
        assert "change_percent_range" in [e.rule for e in res.rejected[0][1]]

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
    def test_snapshot_with_none_metrics_passes(self, validator: IngestionValidator) -> None:
        errors = validator.validate_snapshot(
            _valid_snapshot(turnover=None, total_volume=None, total_transactions=None)
        )
        assert errors == []
# ---------------------------------------------------------------------------
# Historical dataset anomalies (ADBLD83, ADBL, NEPSE specifics)
# ---------------------------------------------------------------------------

class TestHistoricalDatasetAnomalies:
    def test_adbld83_ltp_greater_than_high(self, validator: IngestionValidator) -> None:
        """ADBLD83 2026-06-02: open=1051.90, high=1051.90, low=1051.90, ltp=1083.40.

        Rejected in strict mode, accepted in historical mode.
        """
        rec = _valid_price(
            symbol="ADBLD83",
            date="2026-06-02",
            open=1051.90,
            high=1051.90,
            low=1051.90,
            close=1083.40,
            volume=1,
            turnover=1083.40,
        )
        res_default = validator.validate_prices([rec])
        assert len(res_default.rejected) == 1
        assert "ohlc_consistency" in [e.rule for e in res_default.rejected[0][1]]

        res_strict = validator.validate_prices([rec], mode="strict")
        assert len(res_strict.rejected) == 1

        res_hist = validator.validate_prices([rec], mode="historical")
        assert len(res_hist.rejected) == 1

    def test_adbld83_ltp_less_than_low(self, validator: IngestionValidator) -> None:
        """ADBLD83 2025-11-09: open=1132.90, high=1132.90, low=1132.90, ltp=1110.30.

        Rejected in strict mode, accepted in historical mode.
        """
        rec = _valid_price(
            symbol="ADBLD83",
            date="2025-11-09",
            open=1132.90,
            high=1132.90,
            low=1132.90,
            close=1110.30,
            volume=1,
            turnover=1110.30,
        )
        res_strict = validator.validate_prices([rec], mode="strict")
        assert len(res_strict.rejected) == 1
        assert "ohlc_consistency" in [e.rule for e in res_strict.rejected[0][1]]

        res_hist = validator.validate_prices([rec], mode="historical")
        assert len(res_hist.rejected) == 1

    def test_adbld83_friday_session(self, validator: IngestionValidator) -> None:
        """ADBLD83 2026-08-21 was a Friday trading session in NEPSE historical data.

        Rejected in strict mode, accepted in historical mode.
        """
        rec = _valid_price(
            symbol="ADBLD83",
            date="2026-08-21",
            open=1039.0,
            high=1039.0,
            low=1039.0,
            close=1039.0,
        )
        res_strict = validator.validate_prices([rec], mode="strict")
        assert len(res_strict.rejected) == 1
        assert "date_not_weekend" in [e.rule for e in res_strict.rejected[0][1]]

        res_hist = validator.validate_prices([rec], mode="historical")
        assert len(res_hist.valid) == 1

    def test_adbl_saturday_session_rejected_in_both_modes(self, validator: IngestionValidator) -> None:
        """ADBL 2016-09-03 was a Saturday, which is non-trading and MUST be rejected even in historical mode."""
        rec = _valid_price(
            symbol="ADBL",
            date="2016-09-03",
            open=800.0,
            high=810.0,
            low=795.0,
            close=805.0,
        )
        res_strict = validator.validate_prices([rec], mode="strict")
        assert len(res_strict.rejected) == 1
        assert "date_not_weekend" in [e.rule for e in res_strict.rejected[0][1]]

        res_hist = validator.validate_prices([rec], mode="historical")
        assert len(res_hist.rejected) == 1
        assert "date_not_weekend" in [e.rule for e in res_hist.rejected[0][1]]

    def test_historical_mode_preserves_high_greater_equal_low(self, validator: IngestionValidator) -> None:
        """high < low is fundamentally invalid and MUST be rejected in historical mode."""
        rec = _valid_price(open=500.0, high=480.0, low=520.0, close=500.0)
        res_hist = validator.validate_prices([rec], mode="historical")
        assert len(res_hist.rejected) == 1
        assert "ohlc_consistency" in [e.rule for e in res_hist.rejected[0][1]]

    def test_historical_mode_preserves_positive_price_requirement(self, validator: IngestionValidator) -> None:
        """Zero or negative price is fundamentally invalid and MUST be rejected in historical mode."""
        for field in ("open", "high", "low", "close"):
            zero_rec = _valid_price(**{field: 0.0})
            res_zero = validator.validate_prices([zero_rec], mode="historical")
            assert len(res_zero.rejected) == 1
            assert "price_positive" in [e.rule for e in res_zero.rejected[0][1]]

            neg_rec = _valid_price(**{field: -5.0})
            res_neg = validator.validate_prices([neg_rec], mode="historical")
            assert len(res_neg.rejected) == 1
            assert "price_positive" in [e.rule for e in res_neg.rejected[0][1]]

    def test_historical_mode_preserves_nonnegative_volume_and_turnover(self, validator: IngestionValidator) -> None:
        """Negative volume or turnover MUST be rejected in historical mode."""
        neg_vol = _valid_price(volume=-10)
        res_vol = validator.validate_prices([neg_vol], mode="historical")
        assert len(res_vol.rejected) == 1
        assert "volume_nonnegative" in [e.rule for e in res_vol.rejected[0][1]]

        neg_to = _valid_price(turnover=-50.0)
        res_to = validator.validate_prices([neg_to], mode="historical")
        assert len(res_to.rejected) == 1
        assert "turnover_nonnegative" in [e.rule for e in res_to.rejected[0][1]]

    def test_historical_mode_preserves_symbol_validation(self, validator: IngestionValidator) -> None:
        """Empty or invalid symbol MUST be rejected in historical mode."""
        empty_sym = _valid_price(symbol="")
        res = validator.validate_prices([empty_sym], mode="historical")
        assert len(res.rejected) == 1
        assert "symbol_nonempty" in [e.rule for e in res.rejected[0][1]]

    def test_historical_mode_preserves_date_format_and_future_date_checks(self, validator: IngestionValidator) -> None:
        """Malformed or future dates MUST be rejected in historical mode."""
        malformed = _valid_price(date="2024/01/01")
        res_fmt = validator.validate_prices([malformed], mode="historical")
        assert len(res_fmt.rejected) == 1
        assert "date_format" in [e.rule for e in res_fmt.rejected[0][1]]

        future = _valid_price(date="2099-01-01")
        res_future = validator.validate_prices([future], mode="historical")
        assert len(res_future.rejected) == 1
        assert "date_not_future" in [e.rule for e in res_future.rejected[0][1]]

    def test_historical_mode_preserves_change_percent_bounds(self, validator: IngestionValidator) -> None:
        """Absurd percentage changes MUST be rejected in historical mode."""
        insane = _valid_price(change_percent=5000.0)
        res = validator.validate_prices([insane], mode="historical")
        assert len(res.rejected) == 1
        assert "change_percent_range" in [e.rule for e in res.rejected[0][1]]
