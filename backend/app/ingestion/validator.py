"""IngestionValidator — applies all financial data validation rules.

Rules are applied per-record and return structured ValidationError objects
so callers can report exactly which rule failed, on which field, and why.
"""
import re
from datetime import date as date_type, datetime, timezone

from app.ingestion.models import (
    PriceValidationResult,
    RawPriceRecord,
    RawSnapshotRecord,
    ValidationError,
)

# NEPSE trades Sunday–Thursday; Friday (4) and Saturday (5) are non-trading.
_NEPSE_HOLIDAYS = {4, 5}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,10}$")


class IngestionValidator:
    """Validates raw ingestion records against financial data quality rules."""

    # ------------------------------------------------------------------
    # Price record validation
    # ------------------------------------------------------------------

    def validate_prices(self, records: list[RawPriceRecord]) -> PriceValidationResult:
        """Validate a batch of price records.

        Returns a PriceValidationResult with separate lists for valid records
        and rejected records (each paired with its list of ValidationErrors).
        """
        result = PriceValidationResult()
        today = datetime.now(tz=timezone.utc).date()

        for record in records:
            errors = self._validate_price_record(record, today)
            if errors:
                result.rejected.append((record, errors))
            else:
                result.valid.append(record)

        return result

    def _validate_price_record(
        self, record: RawPriceRecord, today: date_type
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []

        # Symbol — must already be uppercase alphanumeric, 1–10 chars
        if not _SYMBOL_RE.match(record.symbol.strip() if record.symbol else ""):
            errors.append(ValidationError(
                rule="symbol_nonempty",
                field="symbol",
                value=record.symbol,
                message="Symbol must be 1–10 uppercase alphanumeric characters.",
            ))

        # Date format
        parsed_date: date_type | None = None
        if not _DATE_RE.match(record.date):
            errors.append(ValidationError(
                rule="date_format",
                field="date",
                value=record.date,
                message="Date must be in YYYY-MM-DD format.",
            ))
        else:
            try:
                parsed_date = date_type.fromisoformat(record.date)
            except ValueError:
                errors.append(ValidationError(
                    rule="date_format",
                    field="date",
                    value=record.date,
                    message="Date is not a valid calendar date.",
                ))

        if parsed_date is not None:
            if parsed_date > today:
                errors.append(ValidationError(
                    rule="date_not_future",
                    field="date",
                    value=record.date,
                    message=f"Date {record.date} is in the future.",
                ))
            if parsed_date.weekday() in _NEPSE_HOLIDAYS:
                errors.append(ValidationError(
                    rule="date_not_weekend",
                    field="date",
                    value=record.date,
                    message=f"Date {record.date} falls on a NEPSE non-trading day (Fri/Sat).",
                ))

        # Price positivity
        for field_name in ("open", "high", "low", "close"):
            value = getattr(record, field_name)
            if value <= 0:
                errors.append(ValidationError(
                    rule="price_positive",
                    field=field_name,
                    value=value,
                    message=f"{field_name} must be > 0, got {value}.",
                ))

        # OHLC consistency (only if all prices are positive)
        if all(getattr(record, f) > 0 for f in ("open", "high", "low", "close")):
            if record.high < record.low:
                errors.append(ValidationError(
                    rule="ohlc_consistency",
                    field="high/low",
                    value=f"{record.high}/{record.low}",
                    message=f"high ({record.high}) must be >= low ({record.low}).",
                ))
            if record.high < record.open:
                errors.append(ValidationError(
                    rule="ohlc_consistency",
                    field="high/open",
                    value=f"{record.high}/{record.open}",
                    message=f"high ({record.high}) must be >= open ({record.open}).",
                ))
            if record.high < record.close:
                errors.append(ValidationError(
                    rule="ohlc_consistency",
                    field="high/close",
                    value=f"{record.high}/{record.close}",
                    message=f"high ({record.high}) must be >= close ({record.close}).",
                ))
            if record.low > record.open:
                errors.append(ValidationError(
                    rule="ohlc_consistency",
                    field="low/open",
                    value=f"{record.low}/{record.open}",
                    message=f"low ({record.low}) must be <= open ({record.open}).",
                ))
            if record.low > record.close:
                errors.append(ValidationError(
                    rule="ohlc_consistency",
                    field="low/close",
                    value=f"{record.low}/{record.close}",
                    message=f"low ({record.low}) must be <= close ({record.close}).",
                ))

        # Volume
        if record.volume < 0:
            errors.append(ValidationError(
                rule="volume_nonnegative",
                field="volume",
                value=record.volume,
                message=f"volume must be >= 0, got {record.volume}.",
            ))

        # Turnover
        if record.turnover < 0:
            errors.append(ValidationError(
                rule="turnover_nonnegative",
                field="turnover",
                value=record.turnover,
                message=f"turnover must be >= 0, got {record.turnover}.",
            ))

        # Change percent sanity
        if not (-100 < record.change_percent < 1000):
            errors.append(ValidationError(
                rule="change_percent_range",
                field="change_percent",
                value=record.change_percent,
                message=(
                    f"change_percent {record.change_percent} is outside the "
                    "plausible range (-100, 1000)."
                ),
            ))

        return errors

    # ------------------------------------------------------------------
    # Snapshot validation
    # ------------------------------------------------------------------

    def validate_snapshot(self, record: RawSnapshotRecord) -> list[ValidationError]:
        """Validate a market snapshot record. Returns empty list if valid."""
        errors: list[ValidationError] = []

        if record.nepse_index <= 0:
            errors.append(ValidationError(
                rule="snapshot_index_positive",
                field="nepse_index",
                value=record.nepse_index,
                message=f"nepse_index must be > 0, got {record.nepse_index}.",
            ))

        if record.turnover < 0:
            errors.append(ValidationError(
                rule="snapshot_turnover_nonnegative",
                field="turnover",
                value=record.turnover,
                message=f"turnover must be >= 0, got {record.turnover}.",
            ))

        if not record.market_status or not record.market_status.strip():
            errors.append(ValidationError(
                rule="snapshot_status_nonempty",
                field="market_status",
                value=record.market_status,
                message="market_status must be a non-empty string.",
            ))

        return errors
