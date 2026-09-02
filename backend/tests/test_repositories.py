"""Repository unit tests using SQLite in-memory — no PostgreSQL required."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.db.base import Base
from app.db.models import Instrument, MarketSnapshot, DailyPrice
from app.repositories.instrument_repository import PostgresInstrumentRepository
from app.repositories.market_repository import PostgresMarketSnapshotRepository
from app.repositories.price_repository import DailyPriceRow, PostgresDailyPriceRepository


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


# ---------------------------------------------------------------------------
# InstrumentRepository
# ---------------------------------------------------------------------------

class TestInstrumentRepository:
    def test_upsert_and_get_by_symbol(self, session: Session) -> None:
        repo = PostgresInstrumentRepository(session)
        repo.upsert("NABIL", "Nabil Bank Limited")
        session.commit()

        result = repo.get_by_symbol("NABIL")
        assert result is not None
        assert result.symbol == "NABIL"
        assert result.company_name == "Nabil Bank Limited"
        assert result.sector is None

    def test_upsert_updates_existing(self, session: Session) -> None:
        repo = PostgresInstrumentRepository(session)
        repo.upsert("NABIL", "Nabil Bank")
        session.commit()
        repo.upsert("NABIL", "Nabil Bank Limited", sector="Banking")
        session.commit()

        result = repo.get_by_symbol("NABIL")
        assert result is not None
        assert result.company_name == "Nabil Bank Limited"
        assert result.sector == "Banking"

    def test_get_by_symbol_unknown_returns_none(self, session: Session) -> None:
        repo = PostgresInstrumentRepository(session)
        assert repo.get_by_symbol("NONEXIST") is None

    def test_get_all_returns_all_instruments(self, session: Session) -> None:
        repo = PostgresInstrumentRepository(session)
        repo.upsert("NABIL", "Nabil Bank Limited")
        repo.upsert("NTC", "Nepal Telecom")
        session.commit()

        results = repo.get_all()
        symbols = [r.symbol for r in results]
        assert "NABIL" in symbols
        assert "NTC" in symbols
        assert len(results) == 2


# ---------------------------------------------------------------------------
# MarketSnapshotRepository
# ---------------------------------------------------------------------------

class TestMarketSnapshotRepository:
    def test_insert_and_get_latest(self, session: Session) -> None:
        repo = PostgresMarketSnapshotRepository(session)
        captured = datetime(2026, 9, 3, 11, 30, tzinfo=timezone.utc)
        repo.insert(
            nepse_index=2786.42,
            index_change=21.35,
            index_change_percent=0.77,
            turnover=552_907_933.0,
            total_volume=1_241_890,
            total_transactions=38_640,
            market_status="Open",
            captured_at=captured,
        )
        session.commit()

        latest = repo.get_latest()
        assert latest is not None
        assert latest.nepse_index == 2786.42
        assert latest.market_status == "Open"

    def test_get_latest_returns_most_recent(self, session: Session) -> None:
        repo = PostgresMarketSnapshotRepository(session)
        older = datetime(2026, 9, 1, 11, 0, tzinfo=timezone.utc)
        newer = datetime(2026, 9, 3, 11, 30, tzinfo=timezone.utc)
        repo.insert(2700.0, 0.0, 0.0, 0.0, 0, 0, "Closed", older)
        repo.insert(2786.42, 21.35, 0.77, 0.0, 0, 0, "Open", newer)
        session.commit()

        latest = repo.get_latest()
        assert latest is not None
        assert latest.nepse_index == 2786.42

    def test_get_latest_empty_returns_none(self, session: Session) -> None:
        repo = PostgresMarketSnapshotRepository(session)
        assert repo.get_latest() is None


# ---------------------------------------------------------------------------
# DailyPriceRepository
# ---------------------------------------------------------------------------

class TestDailyPriceRepository:
    def _seed_instrument(self, session: Session) -> None:
        repo = PostgresInstrumentRepository(session)
        repo.upsert("NABIL", "Nabil Bank Limited")
        session.commit()

    def test_upsert_many_and_get_by_symbol(self, session: Session) -> None:
        self._seed_instrument(session)
        repo = PostgresDailyPriceRepository(session)
        rows = [
            DailyPriceRow("NABIL", "2026-09-01", 500.0, 510.0, 498.0, 505.0, 100_000, 50_500_000.0),
            DailyPriceRow("NABIL", "2026-09-02", 505.0, 515.0, 503.0, 512.0, 110_000, 56_320_000.0),
        ]
        inserted = repo.upsert_many(rows)
        session.commit()

        assert inserted == 2
        results = repo.get_by_symbol("NABIL")
        assert len(results) == 2
        assert results[0].date == "2026-09-01"
        assert results[1].date == "2026-09-02"

    def test_get_by_symbol_and_date_range(self, session: Session) -> None:
        self._seed_instrument(session)
        repo = PostgresDailyPriceRepository(session)
        rows = [
            DailyPriceRow("NABIL", "2026-08-01", 480.0, 490.0, 478.0, 485.0, 90_000, 43_650_000.0),
            DailyPriceRow("NABIL", "2026-09-01", 500.0, 510.0, 498.0, 505.0, 100_000, 50_500_000.0),
            DailyPriceRow("NABIL", "2026-09-02", 505.0, 515.0, 503.0, 512.0, 110_000, 56_320_000.0),
        ]
        repo.upsert_many(rows)
        session.commit()

        results = repo.get_by_symbol_and_date_range("NABIL", "2026-09-01", "2026-09-02")
        assert len(results) == 2
        assert all(r.date >= "2026-09-01" for r in results)

    def test_get_latest_by_symbol(self, session: Session) -> None:
        self._seed_instrument(session)
        repo = PostgresDailyPriceRepository(session)
        rows = [
            DailyPriceRow("NABIL", "2026-09-01", 500.0, 510.0, 498.0, 505.0, 100_000, 50_500_000.0),
            DailyPriceRow("NABIL", "2026-09-03", 515.0, 520.0, 513.0, 518.0, 120_000, 62_160_000.0),
            DailyPriceRow("NABIL", "2026-09-02", 505.0, 515.0, 503.0, 512.0, 110_000, 56_320_000.0),
        ]
        repo.upsert_many(rows)
        session.commit()

        latest = repo.get_latest_by_symbol("NABIL")
        assert latest is not None
        assert latest.date == "2026-09-03"

    def test_duplicate_symbol_date_is_skipped(self, session: Session) -> None:
        self._seed_instrument(session)
        repo = PostgresDailyPriceRepository(session)
        row = DailyPriceRow("NABIL", "2026-09-01", 500.0, 510.0, 498.0, 505.0, 100_000, 50_500_000.0)
        repo.upsert_many([row])
        session.commit()

        # Insert same row again — should be skipped, not raise.
        inserted = repo.upsert_many([row])
        assert inserted == 0

    def test_get_latest_unknown_symbol_returns_none(self, session: Session) -> None:
        repo = PostgresDailyPriceRepository(session)
        assert repo.get_latest_by_symbol("NONEXIST") is None
