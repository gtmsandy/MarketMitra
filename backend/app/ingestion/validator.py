"""IngestionValidator — applies all financial data validation rules.

Rules are applied per-record and return structured ValidationError objects
so callers can report exactly which rule failed, on which field, and why.
"""

import re
from datetime import date as date_type, datetime, timezone
from typing import Literal

from app.ingestion.models import (
    PriceValidationResult,
    RawPriceRecord,
    RawSnapshotRecord,
    ValidationError,
)

# NEPSE normally trades Sunday–Thursday.
# Strict/live validation rejects Friday and Saturday.
_NEPSE_HOLIDAYS = {4, 5}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,10}$")

ValidationMode = Literal["strict", "historical"]


class IngestionValidator:
    """Validates raw ingestion records against financial data quality rules."""

    # ------------------------------------------------------------------
    # Price record validation
    # ------------------------------------------------------------------

    def validate_prices(
        self,
        records: list[RawPriceRecord],
        mode: ValidationMode = "strict",
    ) -> PriceValidationResult:
        """Validate a batch of price records.

        Args:
            records: Raw price records to validate.
            mode:
                - "strict": Full canonical OHLC validation for live/current data.
                - "historical": Allows known legacy NEPSE anomalies while
                  preserving fundamental data integrity checks.

        Returns:
            PriceValidationResult with valid and rejected records.
        """

        if mode not in ("strict", "historical"):
            raise ValueError(
                f"Invalid validation mode {mode!r}. "
                "Must be 'strict' or 'historical'."
            )

        result = PriceValidationResult()
        today = datetime.now(tz=timezone.utc).date()

        for record in records:
            errors = self._validate_price_record(
                record=record,
                today=today,
                mode=mode,
            )

            if errors:
                result.rejected.append((record, errors))
            else:
                result.valid.append(record)

        return result

    def _validate_price_record(
        self,
        record: RawPriceRecord,
        today: date_type,
        mode: ValidationMode = "strict",
    ) -> list[ValidationError]:
        """Validate one raw price record."""

        errors: list[ValidationError] = []

        # --------------------------------------------------------------
        # Symbol validation
        # --------------------------------------------------------------

        if not _SYMBOL_RE.match(record.symbol.strip() if record.symbol else ""):
            errors.append(
                ValidationError(
                    rule="symbol_nonempty",
                    field="symbol",
                    value=record.symbol,
                    message=(
                        "Symbol must be 1–10 uppercase alphanumeric characters."
                    ),
                )
            )

        # --------------------------------------------------------------
        # Date validation
        # --------------------------------------------------------------

        parsed_date: date_type | None = None

        if not _DATE_RE.match(record.date):
            errors.append(
                ValidationError(
                    rule="date_format",
                    field="date",
                    value=record.date,
                    message="Date must be in YYYY-MM-DD format.",
                )
            )
        else:
            try:
                parsed_date = date_type.fromisoformat(record.date)
            except ValueError:
                errors.append(
                    ValidationError(
                        rule="date_format",
                        field="date",
                        value=record.date,
                        message="Date is not a valid calendar date.",
                    )
                )

        if parsed_date is not None:

            # Future dates are never accepted.
            if parsed_date > today:
                errors.append(
                    ValidationError(
                        rule="date_not_future",
                        field="date",
                        value=record.date,
                        message=f"Date {record.date} is in the future.",
                    )
                )

            # Historical NEPSE data may legitimately contain Friday sessions.
            #
            # Python weekday:
            # Monday=0 ... Friday=4, Saturday=5, Sunday=6
            #
            # Historical mode:
            #   Friday allowed
            #   Saturday rejected
            #
            # Strict mode:
            #   Friday and Saturday rejected
            if mode == "historical":
                invalid_weekdays = {5}
            else:
                invalid_weekdays = _NEPSE_HOLIDAYS

            if parsed_date.weekday() in invalid_weekdays:
                errors.append(
                    ValidationError(
                        rule="date_not_weekend",
                        field="date",
                        value=record.date,
                        message=(
                            f"Date {record.date} falls on a NEPSE "
                            "non-trading day."
                        ),
                    )
                )

        # --------------------------------------------------------------
        # Price positivity
        # --------------------------------------------------------------

        for field_name in ("open", "high", "low", "close"):
            value = getattr(record, field_name)

            if value <= 0:
                errors.append(
                    ValidationError(
                        rule="price_positive",
                        field=field_name,
                        value=value,
                        message=f"{field_name} must be > 0, got {value}.",
                    )
                )

        # --------------------------------------------------------------
        # OHLC consistency
        # --------------------------------------------------------------

        if all(
            getattr(record, field_name) > 0
            for field_name in ("open", "high", "low", "close")
        ):

            # Fundamental market consistency.
            #
            # High must never be below Low.
            # This rule applies in BOTH strict and historical modes.
            if record.high < record.low:
                errors.append(
                    ValidationError(
                        rule="ohlc_consistency",
                        field="high/low",
                        value=f"{record.high}/{record.low}",
                        message=(
                            f"high ({record.high}) must be >= "
                            f"low ({record.low})."
                        ),
                    )
                )

            if mode == "strict":

                # ------------------------------------------------------
                # Strict mode
                # ------------------------------------------------------
                #
                # Canonical/live market data must satisfy complete OHLC
                # bounds.
                #

                if record.high < record.open:
                    errors.append(
                        ValidationError(
                            rule="ohlc_consistency",
                            field="high/open",
                            value=f"{record.high}/{record.open}",
                            message=(
                                f"high ({record.high}) must be >= "
                                f"open ({record.open})."
                            ),
                        )
                    )

                if record.low > record.open:
                    errors.append(
                        ValidationError(
                            rule="ohlc_consistency",
                            field="low/open",
                            value=f"{record.low}/{record.open}",
                            message=(
                                f"low ({record.low}) must be <= "
                                f"open ({record.open})."
                            ),
                        )
                    )

                if record.high < record.close:
                    errors.append(
                        ValidationError(
                            rule="ohlc_consistency",
                            field="high/close",
                            value=f"{record.high}/{record.close}",
                            message=(
                                f"high ({record.high}) must be >= "
                                f"close ({record.close})."
                            ),
                        )
                    )

                if record.low > record.close:
                    errors.append(
                        ValidationError(
                            rule="ohlc_consistency",
                            field="low/close",
                            value=f"{record.low}/{record.close}",
                            message=(
                                f"low ({record.low}) must be <= "
                                f"close ({record.close})."
                            ),
                        )
                    )

        # --------------------------------------------------------------
        # Volume validation
        # --------------------------------------------------------------

        if record.volume < 0:
            errors.append(
                ValidationError(
                    rule="volume_nonnegative",
                    field="volume",
                    value=record.volume,
                    message=f"volume must be >= 0, got {record.volume}.",
                )
            )

        # --------------------------------------------------------------
        # Turnover validation
        # --------------------------------------------------------------

        if record.turnover < 0:
            errors.append(
                ValidationError(
                    rule="turnover_nonnegative",
                    field="turnover",
                    value=record.turnover,
                    message=f"turnover must be >= 0, got {record.turnover}.",
                )
            )

        # --------------------------------------------------------------
        # Percentage change sanity
        # --------------------------------------------------------------

        if not (-100 < record.change_percent < 1000):
            errors.append(
                ValidationError(
                    rule="change_percent_range",
                    field="change_percent",
                    value=record.change_percent,
                    message=(
                        f"change_percent {record.change_percent} is outside "
                        "the plausible range (-100, 1000)."
                    ),
                )
            )

        return errors

    # ------------------------------------------------------------------
    # Snapshot validation
    # ------------------------------------------------------------------

    def validate_snapshot(
        self,
        record: RawSnapshotRecord,
    ) -> list[ValidationError]:
        """Validate a market snapshot record.

        Historical datasets may legitimately omit turnover, total volume,
        and transaction metrics. Missing values are represented as None
        and must remain NULL rather than being replaced with fabricated
        zeros.
        """

        errors: list[ValidationError] = []

        # NEPSE index must be positive.
        if record.nepse_index <= 0:
            errors.append(
                ValidationError(
                    rule="snapshot_index_positive",
                    field="nepse_index",
                    value=record.nepse_index,
                    message=(
                        f"nepse_index must be > 0, got {record.nepse_index}."
                    ),
                )
            )

        # Turnover is nullable for historical snapshots.
        # Validate only when a value is actually available.
        if record.turnover is not None and record.turnover < 0:
            errors.append(
                ValidationError(
                    rule="snapshot_turnover_nonnegative",
                    field="turnover",
                    value=record.turnover,
                    message=(
                        f"turnover must be >= 0, got {record.turnover}."
                    ),
                )
            )

        # Market status must always be present.
        if not record.market_status or not record.market_status.strip():
            errors.append(
                ValidationError(
                    rule="snapshot_status_nonempty",
                    field="market_status",
                    value=record.market_status,
                    message="market_status must be a non-empty string.",
                )
            )

        return errors