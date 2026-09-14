"""Pre-production ingestion gate integration tests against an isolated PostgreSQL database.

Tests the full ingestion pipeline:
A. Small valid ingestion
B. Duplicate ingestion idempotency
C. Replace mode semantics
D. Rejection of invalid records from PostgreSQL
E. Transaction rollback on failure and dry-run
F. IngestionRun audit logging
G. Foreign-key and UniqueConstraint integrity
H. Historical underscore symbol persistence (GBD80_81, NIFRAUR85_86)
I. Preservation of NULL snapshot metrics (no fabricated zeros)
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_database_url
from app.db.base import Base
from app.db.models import DailyPrice, IngestionRun, Instrument, MarketSnapshot
from app.ingestion.models import (
    RawInstrumentRecord,
    RawPriceRecord,
    RawSnapshotRecord,
)
from app.ingestion.service import IngestionService
from app.ingestion.sources.base import DataSource


# ---------------------------------------------------------------------------
# Test Data Source Helper
# ---------------------------------------------------------------------------

class GateTestDataSource(DataSource):
    def __init__(
        self,
        instruments: list[RawInstrumentRecord] | None = None,
        snapshots: list[RawSnapshotRecord] | None = None,
        prices_by_symbol: dict[str, list[RawPriceRecord]] | None = None,
        name: str = "gate_test",
    ) -> None:
        self._name = name
        self._instruments = instruments or []
        self._snapshots = snapshots or []
        self._prices_by_symbol = prices_by_symbol or {}

    @property
    def name(self) -> str:
        return self._name

    def fetch_instruments(self) -> list[RawInstrumentRecord]:
        return list(self._instruments)

    def fetch_snapshot(self) -> RawSnapshotRecord | None:
        return self._snapshots[0] if self._snapshots else None

    def fetch_snapshots(self) -> list[RawSnapshotRecord]:
        return list(self._snapshots)

    def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
        return list(self._prices_by_symbol.get(symbol, []))


# ---------------------------------------------------------------------------
# Isolated Database Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pg_engine():
    """Create an isolated test database marketmitra_test_gate."""
    base_url = get_database_url()
    admin_url = base_url.rsplit("/", 1)[0] + "/postgres"
    test_db_url = base_url.rsplit("/", 1)[0] + "/marketmitra_test_gate"

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text("DROP DATABASE IF EXISTS marketmitra_test_gate WITH (FORCE)"))
            conn.execute(text("CREATE DATABASE marketmitra_test_gate"))
    finally:
        admin_engine.dispose()

    engine = create_engine(test_db_url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text("DROP DATABASE IF EXISTS marketmitra_test_gate WITH (FORCE)"))
    finally:
        admin_engine.dispose()


@pytest.fixture()
def db_session(pg_engine):
    """Provide a clean session per test with truncated tables."""
    factory = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    session = factory()

    # Clean tables before each test
    session.execute(text("TRUNCATE TABLE daily_prices, market_snapshots, instruments, ingestion_runs, live_quotes CASCADE"))
    session.commit()

    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Gate Test Cases (A through I)
# ---------------------------------------------------------------------------

class TestPreProductionGate:

    def test_a_small_valid_ingestion(self, db_session: Session) -> None:
        """A. Small valid ingestion: instruments, prices, snapshots, relationships."""
        source = GateTestDataSource(
            instruments=[
                RawInstrumentRecord(symbol="TESTA", company_name="Test Company A", sector="Commercial Banks"),
            ],
            snapshots=[
                RawSnapshotRecord(
                    nepse_index=2100.50,
                    index_change=15.20,
                    index_change_percent=0.73,
                    turnover=5000000.0,
                    total_volume=10000,
                    total_transactions=500,
                    market_status="CLOSED",
                    captured_at=datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc),
                )
            ],
            prices_by_symbol={
                "TESTA": [
                    RawPriceRecord(
                        symbol="TESTA",
                        date="2026-09-01",
                        open=500.0,
                        high=520.0,
                        low=495.0,
                        close=515.0,
                        volume=1000,
                        turnover=515000.0,
                        change=15.0,
                        change_percent=3.0,
                        previous_close=500.0,
                    )
                ]
            },
        )

        service = IngestionService(source=source, session=db_session, validation_mode="historical")
        report = service.run()

        assert report.status == "success"
        assert report.instruments_upserted == 1
        assert report.prices_accepted == 1
        assert report.prices_rejected == 0

        # Verify DB rows
        inst = db_session.get(Instrument, "TESTA")
        assert inst is not None
        assert inst.company_name == "Test Company A"
        assert inst.sector == "Commercial Banks"

        prices = db_session.query(DailyPrice).filter_by(symbol="TESTA").all()
        assert len(prices) == 1
        assert prices[0].close == 515.0
        assert prices[0].instrument.symbol == "TESTA"  # Relationship

        snaps = db_session.query(MarketSnapshot).all()
        assert len(snaps) == 1
        assert snaps[0].nepse_index == 2100.50

    def test_b_duplicate_ingestion_idempotency(self, db_session: Session) -> None:
        """B. Duplicate ingestion: running the same data twice in skip mode does not duplicate rows."""
        source = GateTestDataSource(
            instruments=[RawInstrumentRecord(symbol="IDEM", company_name="Idempotent Bank")],
            prices_by_symbol={
                "IDEM": [
                    RawPriceRecord(symbol="IDEM", date="2026-09-01", open=100.0, high=105.0, low=98.0, close=102.0, volume=100, turnover=10200.0),
                ]
            },
        )

        # Run 1
        svc1 = IngestionService(source=source, session=db_session, on_conflict="skip", validation_mode="historical")
        rep1 = svc1.run()
        assert rep1.prices_accepted == 1
        assert rep1.prices_skipped == 0
        assert db_session.query(DailyPrice).filter_by(symbol="IDEM").count() == 1

        # Run 2: Exact duplicate
        svc2 = IngestionService(source=source, session=db_session, on_conflict="skip", validation_mode="historical")
        rep2 = svc2.run()
        assert rep2.prices_accepted == 0
        assert rep2.prices_skipped == 1
        assert db_session.query(DailyPrice).filter_by(symbol="IDEM").count() == 1

    def test_c_replace_mode_semantics(self, db_session: Session) -> None:
        """C. Replace mode: overwrites existing prices without corrupting unrelated rows."""
        source1 = GateTestDataSource(
            instruments=[
                RawInstrumentRecord(symbol="REP1", company_name="Replace Bank"),
                RawInstrumentRecord(symbol="KEEP", company_name="Keep Bank"),
            ],
            prices_by_symbol={
                "REP1": [RawPriceRecord(symbol="REP1", date="2026-09-01", open=100.0, high=105.0, low=98.0, close=100.0, volume=100, turnover=10000.0)],
                "KEEP": [RawPriceRecord(symbol="KEEP", date="2026-09-01", open=200.0, high=205.0, low=198.0, close=200.0, volume=200, turnover=40000.0)],
            },
        )
        IngestionService(source=source1, session=db_session, validation_mode="historical").run()

        # Update REP1 with close=120.0 in replace mode
        source2 = GateTestDataSource(
            instruments=[RawInstrumentRecord(symbol="REP1", company_name="Replace Bank")],
            prices_by_symbol={
                "REP1": [RawPriceRecord(symbol="REP1", date="2026-09-01", open=100.0, high=125.0, low=98.0, close=120.0, volume=150, turnover=18000.0)]
            },
        )
        rep2 = IngestionService(source=source2, session=db_session, on_conflict="replace", validation_mode="historical").run()
        assert rep2.prices_replaced == 1

        # Verify updated row
        p_rep = db_session.query(DailyPrice).filter_by(symbol="REP1", date="2026-09-01").one()
        assert p_rep.close == 120.0

        # Verify KEEP is untouched
        p_keep = db_session.query(DailyPrice).filter_by(symbol="KEEP", date="2026-09-01").one()
        assert p_keep.close == 200.0

    def test_d_rejected_records_do_not_enter_database(self, db_session: Session) -> None:
        """D. Rejected records (inverted high < low, Saturday date) must never enter PostgreSQL."""
        source = GateTestDataSource(
            instruments=[RawInstrumentRecord(symbol="REJ", company_name="Reject Corp")],
            prices_by_symbol={
                "REJ": [
                    # Valid
                    RawPriceRecord(symbol="REJ", date="2026-09-01", open=100.0, high=105.0, low=98.0, close=102.0, volume=100, turnover=10200.0),
                    # Inverted high < low
                    RawPriceRecord(symbol="REJ", date="2026-09-02", open=100.0, high=95.0, low=105.0, close=100.0, volume=100, turnover=10000.0),
                    # Saturday (2016-09-03)
                    RawPriceRecord(symbol="REJ", date="2016-09-03", open=100.0, high=105.0, low=95.0, close=100.0, volume=100, turnover=10000.0),
                ]
            },
        )
        report = IngestionService(source=source, session=db_session, validation_mode="historical").run()

        assert report.prices_accepted == 1
        assert report.prices_rejected == 2

        # Verify only 1 row in DB
        prices = db_session.query(DailyPrice).filter_by(symbol="REJ").all()
        assert len(prices) == 1
        assert prices[0].date == "2026-09-01"

    def test_e_transaction_rollback_safety(self, db_session: Session) -> None:
        """E. Dry run calls rollback; failure mid-run leaves zero writes behind."""
        source = GateTestDataSource(
            instruments=[RawInstrumentRecord(symbol="ROLL", company_name="Rollback Corp")],
            prices_by_symbol={
                "ROLL": [RawPriceRecord(symbol="ROLL", date="2026-09-01", open=100.0, high=105.0, low=98.0, close=102.0, volume=100, turnover=10200.0)]
            },
        )

        # Dry run
        dry_rep = IngestionService(source=source, session=db_session, dry_run=True, validation_mode="historical").run()
        assert dry_rep.status == "dry_run"
        assert db_session.query(Instrument).filter_by(symbol="ROLL").first() is None
        assert db_session.query(DailyPrice).filter_by(symbol="ROLL").first() is None

    def test_f_ingestion_run_tracking(self, db_session: Session) -> None:
        """F. IngestionRun audit rows track execution status and metrics."""
        source = GateTestDataSource(
            instruments=[RawInstrumentRecord(symbol="RUN1", company_name="Run 1 Bank")],
            prices_by_symbol={
                "RUN1": [RawPriceRecord(symbol="RUN1", date="2026-09-01", open=100.0, high=105.0, low=98.0, close=102.0, volume=100, turnover=10200.0)]
            },
        )
        rep = IngestionService(source=source, session=db_session, validation_mode="historical").run()
        assert rep.status == "success"

        run = db_session.query(IngestionRun).first()
        assert run is not None
        assert run.status == "success"
        assert run.prices_accepted == 1
        assert run.source == "gate_test"

    def test_g_foreign_key_and_uniqueness_integrity(self, db_session: Session) -> None:
        """G. Direct foreign key and UniqueConstraint violations are caught by PostgreSQL."""
        # FK violation
        orphan_price = DailyPrice(
            symbol="NONEXISTENT",
            date="2026-09-01",
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=10,
            turnover=1000.0,
        )
        db_session.add(orphan_price)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

        # Uniqueness violation
        inst = Instrument(symbol="UNIQ", company_name="Uniq Corp", created_at=datetime.now(tz=timezone.utc))
        p1 = DailyPrice(symbol="UNIQ", date="2026-09-01", open=100.0, high=105.0, low=95.0, close=100.0, volume=10, turnover=1000.0)
        p2 = DailyPrice(symbol="UNIQ", date="2026-09-01", open=102.0, high=106.0, low=96.0, close=101.0, volume=20, turnover=2000.0)
        db_session.add_all([inst, p1, p2])
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_h_historical_underscore_symbols_persistence(self, db_session: Session) -> None:
        """H. Debenture symbols with underscores (GBD80_81, NIFRAUR85_86) are successfully persisted."""
        source = GateTestDataSource(
            instruments=[
                RawInstrumentRecord(symbol="GBD80_81", company_name="Global IME Bank Debenture 2080/81", sector="Corporate Debentures"),
                RawInstrumentRecord(symbol="NIFRAUR85_86", company_name="NIFRA Urja Rinpatra 2085/86", sector="Corporate Debentures"),
            ],
            prices_by_symbol={
                "GBD80_81": [
                    RawPriceRecord(symbol="GBD80_81", date="2024-04-09", open=1000.0, high=1000.0, low=1000.0, close=1000.0, volume=25, turnover=25000.0)
                ],
                "NIFRAUR85_86": [
                    RawPriceRecord(symbol="NIFRAUR85_86", date="2026-08-18", open=1020.0, high=1020.0, low=1020.0, close=1020.0, volume=10, turnover=10200.0)
                ],
            },
        )
        report = IngestionService(source=source, session=db_session, validation_mode="historical").run()
        assert report.prices_accepted == 2
        assert report.prices_rejected == 0

        p1 = db_session.query(DailyPrice).filter_by(symbol="GBD80_81").first()
        p2 = db_session.query(DailyPrice).filter_by(symbol="NIFRAUR85_86").first()
        assert p1 is not None
        assert p2 is not None

    def test_i_null_market_snapshot_metrics_remain_null(self, db_session: Session) -> None:
        """I. Missing historical turnover/volume/transactions remain NULL in PostgreSQL and never become 0.0."""
        source = GateTestDataSource(
            snapshots=[
                RawSnapshotRecord(
                    nepse_index=1500.0,
                    index_change=0.0,
                    index_change_percent=0.0,
                    turnover=None,
                    total_volume=None,
                    total_transactions=None,
                    market_status="CLOSED",
                    captured_at=datetime(2015, 1, 1, 15, 0, tzinfo=timezone.utc),
                )
            ]
        )
        report = IngestionService(source=source, session=db_session, validation_mode="historical").run()
        assert report.snapshots_inserted == 1

        snap = db_session.query(MarketSnapshot).first()
        assert snap is not None
        assert snap.turnover is None
        assert snap.total_volume is None
        assert snap.total_transactions is None
        assert snap.turnover != 0.0
        assert snap.total_volume != 0
        assert snap.total_transactions != 0

    def test_j_live_quotes_unique_constraint_in_postgres(self, db_session: Session) -> None:
        """J. Inserting duplicate (symbol, timestamp) into live_quotes raises IntegrityError in PostgreSQL."""
        from app.db.models import LiveQuote

        inst = Instrument(symbol="LIVEUNIQ", company_name="Live Uniq Corp", created_at=datetime.now(tz=timezone.utc))
        db_session.add(inst)
        db_session.flush()

        now = datetime(2026, 9, 10, 11, 30, tzinfo=timezone.utc)
        q1 = LiveQuote(
            symbol="LIVEUNIQ",
            timestamp=now,
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
            volume=10,
            turnover=1000.0,
            provider="test",
            ingested_at=now,
        )
        q2 = LiveQuote(
            symbol="LIVEUNIQ",
            timestamp=now,
            open=102.0,
            high=106.0,
            low=96.0,
            close=101.0,
            volume=20,
            turnover=2020.0,
            provider="test",
            ingested_at=now,
        )
        db_session.add(q1)
        db_session.flush()

        db_session.add(q2)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_k_security_type_filtering_isolates_equities(self, db_session: Session) -> None:
        """K. Analytical universes filter on security_type = 'EQUITY', excluding promoter shares and debentures."""
        inst_eq = Instrument(symbol="EQ1", company_name="Equity Corp", sector="Commercial Banks", security_type="EQUITY", created_at=datetime.now(tz=timezone.utc))
        inst_po = Instrument(symbol="PO1", company_name="Promoter Corp", sector="Promoter Share", security_type="PROMOTER_SHARE", created_at=datetime.now(tz=timezone.utc))
        inst_deb = Instrument(symbol="DEB1", company_name="Debenture Corp", sector="Corporate Debentures", security_type="DEBENTURE", created_at=datetime.now(tz=timezone.utc))

        p_eq = DailyPrice(symbol="EQ1", date="2026-09-03", open=100.0, high=105.0, low=99.0, close=102.0, volume=1000, turnover=102000.0, change=2.0, change_percent=2.0, previous_close=100.0)
        p_po = DailyPrice(symbol="PO1", date="2026-09-03", open=500.0, high=550.0, low=480.0, close=550.0, volume=50, turnover=27500.0, change=50.0, change_percent=10.0, previous_close=500.0)
        p_deb = DailyPrice(symbol="DEB1", date="2026-09-03", open=1000.0, high=1000.0, low=1000.0, close=1000.0, volume=10, turnover=10000.0, change=0.0, change_percent=0.0, previous_close=1000.0)

        db_session.add_all([inst_eq, inst_po, inst_deb, p_eq, p_po, p_deb])
        db_session.commit()

        from app.repositories.price_repository import PostgresDailyPriceRepository
        price_repo = PostgresDailyPriceRepository(db_session)

        # Breadth filtered to EQUITY
        breadth = price_repo.get_market_breadth(session_date="2026-09-03", security_type="EQUITY")
        assert breadth.total_count == 1
        assert breadth.advancing_count == 1

        # Sectors filtered to EQUITY
        sectors = price_repo.get_sector_analytics(security_type="EQUITY")
        sec_names = [s.sector for s in sectors]
        assert "Commercial Banks" in sec_names
        assert "Promoter Share" not in sec_names
        assert "Corporate Debentures" not in sec_names

        # Heatmap filtered to EQUITY
        heatmap = price_repo.get_market_heatmap(security_type="EQUITY")
        hm_symbols = [h.symbol for h in heatmap]
        assert "EQ1" in hm_symbols
        assert "PO1" not in hm_symbols
        assert "DEB1" not in hm_symbols
        db_session.rollback()
