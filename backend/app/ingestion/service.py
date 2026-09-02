"""IngestionService — orchestrates the full ingestion pipeline.

Flow per run:
    1. Fetch instruments, snapshot, and price records from the DataSource.
    2. Validate all records through IngestionValidator.
    3. Persist valid records through the repository layer.
    4. Write an IngestionRun audit record.
    5. Return a structured IngestionReport.

The service owns no knowledge of SQL, HTTP, or file I/O.  It depends on
the DataSource and repository abstractions only.
"""
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.ingestion.models import IngestionReport, RawPriceRecord, ValidationError
from app.ingestion.sources.base import DataSource
from app.ingestion.validator import IngestionValidator
from app.repositories.ingestion_run_repository import PostgresIngestionRunRepository
from app.repositories.instrument_repository import PostgresInstrumentRepository
from app.repositories.market_repository import PostgresMarketSnapshotRepository
from app.repositories.price_repository import (
    DailyPriceRow,
    PostgresDailyPriceRepository,
)


class IngestionService:
    """Orchestrates one complete ingestion run from a DataSource into the DB."""

    def __init__(
        self,
        source: DataSource,
        session: Session,
        on_conflict: Literal["skip", "replace"] = "skip",
    ) -> None:
        self._source = source
        self._session = session
        self._on_conflict = on_conflict
        self._validator = IngestionValidator()
        self._instruments = PostgresInstrumentRepository(session)
        self._snapshots = PostgresMarketSnapshotRepository(session)
        self._prices = PostgresDailyPriceRepository(session)
        self._runs = PostgresIngestionRunRepository(session)

    def run(self) -> IngestionReport:
        """Execute a full ingestion run and return a structured report."""
        started_at = datetime.now(tz=timezone.utc)

        try:
            report = self._execute(started_at)
        except Exception as exc:
            finished_at = datetime.now(tz=timezone.utc)
            report = IngestionReport(
                source=self._source.name,
                started_at=started_at,
                finished_at=finished_at,
                status="failure",
                error_detail=str(exc),
            )
            try:
                self._runs.record(report)
                self._session.commit()
            except Exception:
                self._session.rollback()

        return report

    def _execute(self, started_at: datetime) -> IngestionReport:
        report = IngestionReport(
            source=self._source.name,
            started_at=started_at,
            finished_at=started_at,  # updated at end
            status="success",
        )

        # --- 1. Instruments --------------------------------------------------
        raw_instruments = self._source.fetch_instruments()
        for rec in raw_instruments:
            self._instruments.upsert(
                symbol=rec.symbol,
                company_name=rec.company_name,
                sector=rec.sector,
            )
        self._session.flush()
        report.instruments_upserted = len(raw_instruments)

        # --- 2. Snapshot ------------------------------------------------------
        raw_snapshot = self._source.fetch_snapshot()
        snapshot_errors = self._validator.validate_snapshot(raw_snapshot)
        if not snapshot_errors:
            _, was_inserted = self._snapshots.insert_if_new_day(
                nepse_index=raw_snapshot.nepse_index,
                index_change=raw_snapshot.index_change,
                index_change_percent=raw_snapshot.index_change_percent,
                turnover=raw_snapshot.turnover,
                total_volume=raw_snapshot.total_volume,
                total_transactions=raw_snapshot.total_transactions,
                market_status=raw_snapshot.market_status,
                captured_at=raw_snapshot.captured_at,
            )
            self._session.flush()
            if was_inserted:
                report.snapshots_inserted = 1
            else:
                report.snapshots_skipped = 1

        # --- 3. Prices --------------------------------------------------------
        all_rejection_summaries: list[str] = []

        for instrument in self._instruments.get_all():
            raw_prices = self._source.fetch_prices(instrument.symbol)
            if not raw_prices:
                continue

            validation_result = self._validator.validate_prices(raw_prices)

            # Collect rejection summaries for the report
            for rejected_record, errors in validation_result.rejected:
                summary = self._format_rejection(rejected_record, errors)
                all_rejection_summaries.append(summary)
            report.prices_rejected += len(validation_result.rejected)

            # Persist valid records
            rows = [self._to_price_row(r) for r in validation_result.valid]
            if rows:
                upsert_result = self._prices.upsert_many(rows, on_conflict=self._on_conflict)
                report.prices_accepted += upsert_result.inserted + upsert_result.replaced
                report.prices_skipped += upsert_result.skipped
                report.prices_replaced += upsert_result.replaced

        report.rejection_summary = all_rejection_summaries

        # --- 4. Audit record --------------------------------------------------
        report.finished_at = datetime.now(tz=timezone.utc)
        self._runs.record(report)
        self._session.commit()

        return report

    @staticmethod
    def _to_price_row(record: RawPriceRecord) -> DailyPriceRow:
        return DailyPriceRow(
            symbol=record.symbol,
            date=record.date,
            open=record.open,
            high=record.high,
            low=record.low,
            close=record.close,
            volume=record.volume,
            turnover=record.turnover,
            change=record.change,
            change_percent=record.change_percent,
            previous_close=record.previous_close,
        )

    @staticmethod
    def _format_rejection(record: RawPriceRecord, errors: list[ValidationError]) -> str:
        rule_names = ", ".join(e.rule for e in errors)
        return f"{record.symbol} {record.date}: [{rule_names}]"
