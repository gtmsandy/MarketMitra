"""Integration tests for IngestionService using SQLite in-memory."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.ingestion.models import RawInstrumentRecord, RawPriceRecord, RawSnapshotRecord
from app.ingestion.service import IngestionService
from app.ingestion.sources.base import DataSource
from app.ingestion.sources.mock_source import MockDataSource
from app.repositories.ingestion_run_repository import PostgresIngestionRunRepository
from app.repositories.price_repository import PostgresDailyPriceRepository


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


def _make_service(session: Session, source: DataSource | None = None, on_conflict="insert") -> IngestionService:
    return IngestionService(
        source=source or MockDataSource(),
        session=session,
        on_conflict=on_conflict,
    )


# ---------------------------------------------------------------------------
# Happy path — MockDataSource
# ---------------------------------------------------------------------------

class TestIngestionServiceMockSource:
    def test_run_produces_success_report(self, session: Session) -> None:
        report = _make_service(session).run()
        assert report.status == "success"
        assert report.source == "mock"
        assert report.error_detail is None

    def test_instruments_upserted(self, session: Session) -> None:
        report = _make_service(session).run()
        assert report.instruments_upserted == 8  # MockMarketProvider has 8 stocks

    def test_snapshot_inserted_first_run(self, session: Session) -> None:
        report = _make_service(session).run()
        assert report.snapshots_inserted == 1
        assert report.snapshots_skipped == 0

    def test_snapshot_skipped_second_run(self, session: Session) -> None:
        _make_service(session).run()
        report = _make_service(session).run()
        assert report.snapshots_inserted == 0
        assert report.snapshots_skipped == 1

    def test_prices_accepted_first_run(self, session: Session) -> None:
        report = _make_service(session).run()
        # 8 instruments × up to 180 days; some may be rejected as date_not_future
        # depending on when MockMarketProvider's MOCK_END_DATE falls relative to UTC today.
        assert report.prices_accepted > 0
        assert report.prices_accepted + report.prices_rejected == 8 * 180

    def test_prices_skipped_on_second_insert_run(self, session: Session) -> None:
        first = _make_service(session).run()
        report = _make_service(session).run()
        assert report.prices_skipped == first.prices_accepted
        assert report.prices_accepted == 0

    def test_prices_replaced_on_replace_run(self, session: Session) -> None:
        first = _make_service(session).run()
        report = _make_service(session, on_conflict="replace").run()
        assert report.prices_replaced == first.prices_accepted
        assert report.prices_skipped == 0

    def test_report_timestamps_set(self, session: Session) -> None:
        report = _make_service(session).run()
        assert report.started_at <= report.finished_at

    def test_ingestion_run_audit_row_written(self, session: Session) -> None:
        first = _make_service(session).run()
        runs_repo = PostgresIngestionRunRepository(session)
        latest = runs_repo.get_latest()
        assert latest is not None
        assert latest.status == "success"
        assert latest.source == "mock"
        assert latest.instruments_upserted == 8
        assert latest.prices_accepted == first.prices_accepted

    def test_no_prices_rejected_except_future_dates(self, session: Session) -> None:
        report = _make_service(session).run()
        # Only date_not_future rejections are expected from mock data (MOCK_END_DATE may be today).
        for summary in report.rejection_summary:
            assert "date_not_future" in summary, f"Unexpected rejection: {summary}"


# ---------------------------------------------------------------------------
# Rejection handling
# ---------------------------------------------------------------------------

class TestIngestionServiceRejections:
    def test_rejected_records_counted_not_persisted(self, session: Session) -> None:
        """A source with one bad price row should reject it and not persist it."""

        class BrokenPriceSource(DataSource):
            @property
            def name(self) -> str:
                return "broken_test"

            def fetch_instruments(self) -> list[RawInstrumentRecord]:
                return [RawInstrumentRecord(symbol="NABIL", company_name="Nabil Bank")]

            def fetch_snapshot(self) -> RawSnapshotRecord:
                return RawSnapshotRecord(
                    nepse_index=2786.0,
                    index_change=0.0,
                    index_change_percent=0.0,
                    turnover=0.0,
                    total_volume=0,
                    total_transactions=0,
                    market_status="Open",
                    captured_at=datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc),
                )

            def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
                return [
                    # valid
                    RawPriceRecord("NABIL", "2026-09-01", 500.0, 520.0, 498.0, 515.0, 10000, 5_150_000.0),
                    # invalid — high < low
                    RawPriceRecord("NABIL", "2026-09-02", 500.0, 480.0, 510.0, 490.0, 10000, 4_900_000.0),
                ]

        report = IngestionService(BrokenPriceSource(), session).run()
        assert report.status == "success"
        assert report.prices_accepted == 1
        assert report.prices_rejected == 1
        assert len(report.rejection_summary) == 1
        assert "ohlc_consistency" in report.rejection_summary[0]

        # Confirm only the valid row was persisted
        prices_repo = PostgresDailyPriceRepository(session)
        rows = prices_repo.get_by_symbol("NABIL")
        assert len(rows) == 1
        assert rows[0].date == "2026-09-01"

    def test_rejection_summary_format(self, session: Session) -> None:
        class SingleBadSource(DataSource):
            @property
            def name(self) -> str:
                return "bad"

            def fetch_instruments(self) -> list[RawInstrumentRecord]:
                return [RawInstrumentRecord(symbol="NTC", company_name="Nepal Telecom")]

            def fetch_snapshot(self) -> RawSnapshotRecord:
                return RawSnapshotRecord(2700.0, 0.0, 0.0, 0.0, 0, 0, "Closed",
                                         datetime(2026, 9, 1, tzinfo=timezone.utc))

            def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
                return [RawPriceRecord("NTC", "2026-09-01", 0.0, 0.0, 0.0, 0.0, 0, 0.0)]

        report = IngestionService(SingleBadSource(), session).run()
        assert report.prices_rejected == 1
        assert "NTC" in report.rejection_summary[0]
        assert "2026-09-01" in report.rejection_summary[0]


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------

class TestIngestionServiceFailure:
    def test_source_exception_produces_failure_report(self, session: Session) -> None:
        class FailingSource(DataSource):
            @property
            def name(self) -> str:
                return "failing"

            def fetch_instruments(self) -> list[RawInstrumentRecord]:
                raise RuntimeError("Simulated source failure")

            def fetch_snapshot(self) -> RawSnapshotRecord:
                raise NotImplementedError

            def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
                raise NotImplementedError

        report = IngestionService(FailingSource(), session).run()
        assert report.status == "failure"
        assert "Simulated source failure" in (report.error_detail or "")
        assert report.prices_accepted == 0

    def test_failure_audit_row_written(self, session: Session) -> None:
        class FailingSource(DataSource):
            @property
            def name(self) -> str:
                return "failing"

            def fetch_instruments(self) -> list[RawInstrumentRecord]:
                raise RuntimeError("boom")

            def fetch_snapshot(self) -> RawSnapshotRecord:
                raise NotImplementedError

            def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
                raise NotImplementedError

        IngestionService(FailingSource(), session).run()
        runs_repo = PostgresIngestionRunRepository(session)
        latest = runs_repo.get_latest()
        assert latest is not None
        assert latest.status == "failure"
        assert latest.error_detail is not None
