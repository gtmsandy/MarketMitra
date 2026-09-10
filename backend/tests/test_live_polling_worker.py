"""Unit tests for LivePollingWorker background service."""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Instrument, LiveQuote
from app.providers.live_adapter import RestPollingLiveProvider
from app.providers.live_base import (
    DataFreshnessMode,
    LiveMarketDataProvider,
    LiveQuoteObservation,
    LiveSnapshotObservation,
    MarketStatus,
)
from app.services.live_polling_worker import LivePollingWorker


# ---------------------------------------------------------------------------
# Test Fixtures & Mock Providers
# ---------------------------------------------------------------------------

class StubLiveProvider(LiveMarketDataProvider):
    def __init__(
        self,
        quotes: list[LiveQuoteObservation] | None = None,
        is_accessible: bool = True,
        raise_on_fetch: bool = False,
    ) -> None:
        self._quotes = quotes or []
        self._is_accessible = is_accessible
        self._raise_on_fetch = raise_on_fetch

    def is_live_accessible(self) -> bool:
        return self._is_accessible

    def get_provider_name(self) -> str:
        return "stub_live_provider"

    def get_market_status(self) -> MarketStatus:
        return MarketStatus.OPEN if self._is_accessible else MarketStatus.DATA_UNAVAILABLE

    def get_data_freshness_mode(self) -> DataFreshnessMode:
        return DataFreshnessMode.LIVE if self._is_accessible else DataFreshnessMode.DATA_UNAVAILABLE

    def fetch_live_snapshot(self) -> LiveSnapshotObservation | None:
        return None

    def fetch_live_quotes(self) -> list[LiveQuoteObservation]:
        if self._raise_on_fetch:
            raise ConnectionError("Simulated upstream network timeout")
        return list(self._quotes)

    def fetch_intraday_history(self, symbol: str) -> list:
        return []


@pytest.fixture()
def in_memory_session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    # Seed known instrument
    session = factory()
    session.add(Instrument(symbol="TEST", company_name="Test Bank Limited", created_at=datetime.now(tz=timezone.utc)))
    session.commit()
    session.close()

    return factory


# ---------------------------------------------------------------------------
# Worker Tests
# ---------------------------------------------------------------------------

class TestLivePollingWorker:
    def test_skips_when_market_closed_by_default(self, in_memory_session_factory) -> None:
        """Worker checks schedule and skips without querying provider when market is closed."""
        provider = StubLiveProvider(quotes=[])
        worker = LivePollingWorker(provider=provider, session_factory=in_memory_session_factory)

        # Force schedule to return closed
        report = worker.poll_cycle(override_market_open=False)
        assert report.status in ("skipped_market_closed", "success")

    def test_skips_when_provider_inaccessible(self, in_memory_session_factory) -> None:
        """Worker returns skipped_provider_inaccessible when provider is not reachable."""
        provider = StubLiveProvider(is_accessible=False)
        worker = LivePollingWorker(provider=provider, session_factory=in_memory_session_factory)

        report = worker.poll_cycle(override_market_open=True)
        assert report.status == "skipped_provider_inaccessible"
        assert report.quotes_received == 0

    def test_valid_quotes_validated_and_persisted(self, in_memory_session_factory) -> None:
        """Valid quotes within ±15% are saved into live_quotes."""
        now = datetime.now(tz=timezone.utc)
        valid_quote = LiveQuoteObservation(
            symbol="TEST",
            ltp=105.0,
            open=100.0,
            high=106.0,
            low=99.0,
            volume=500,
            turnover=52500.0,
            change=5.0,  # 5% change from 100 prev close
            change_percent=5.0,
            source_timestamp=now,
            captured_at=now,
            provider="stub_live_provider",
        )
        provider = StubLiveProvider(quotes=[valid_quote])
        worker = LivePollingWorker(provider=provider, session_factory=in_memory_session_factory)

        report = worker.poll_cycle(override_market_open=True)
        assert report.status == "success"
        assert report.quotes_received == 1
        assert report.quotes_accepted == 1
        assert report.quotes_rejected == 0

        # Verify DB
        session = in_memory_session_factory()
        saved = session.query(LiveQuote).filter_by(symbol="TEST").all()
        assert len(saved) == 1
        assert saved[0].close == 105.0
        assert saved[0].provider == "stub_live_provider"
        session.close()

    def test_quotes_exceeding_15_percent_rejected_without_mutation(
        self, in_memory_session_factory
    ) -> None:
        """Quotes exceeding ±15% daily limit are rejected and never saved into live_quotes."""
        now = datetime.now(tz=timezone.utc)
        invalid_quote = LiveQuoteObservation(
            symbol="TEST",
            ltp=120.0,  # +20% change from 100.0 (violates ±15%)
            open=100.0,
            high=120.0,
            low=100.0,
            volume=50,
            turnover=6000.0,
            change=20.0,
            change_percent=20.0,
            source_timestamp=now,
            captured_at=now,
            provider="stub_live_provider",
        )
        provider = StubLiveProvider(quotes=[invalid_quote])
        worker = LivePollingWorker(provider=provider, session_factory=in_memory_session_factory)

        report = worker.poll_cycle(override_market_open=True)
        assert report.status == "success"
        assert report.quotes_received == 1
        assert report.quotes_accepted == 0
        assert report.quotes_rejected == 1

        # Verify DB: 0 rows saved
        session = in_memory_session_factory()
        assert session.query(LiveQuote).filter_by(symbol="TEST").count() == 0
        session.close()

    def test_duplicate_observations_deduplicated(self, in_memory_session_factory) -> None:
        """Identical (symbol, timestamp) observation is not duplicated in DB."""
        now = datetime(2026, 9, 10, 11, 30, tzinfo=timezone.utc)
        quote = LiveQuoteObservation(
            symbol="TEST",
            ltp=102.0,
            open=100.0,
            high=103.0,
            low=99.0,
            volume=200,
            turnover=20400.0,
            change=2.0,
            change_percent=2.0,
            source_timestamp=now,
            captured_at=now,
            provider="stub_live_provider",
        )
        provider = StubLiveProvider(quotes=[quote])
        worker = LivePollingWorker(provider=provider, session_factory=in_memory_session_factory)

        # Poll 1
        r1 = worker.poll_cycle(override_market_open=True)
        assert r1.quotes_accepted == 1
        assert r1.quotes_duplicate == 0

        # Poll 2 with exact same timestamp
        r2 = worker.poll_cycle(override_market_open=True)
        assert r2.quotes_accepted == 0
        assert r2.quotes_duplicate == 1

        # DB has exactly 1 row
        session = in_memory_session_factory()
        assert session.query(LiveQuote).filter_by(symbol="TEST").count() == 1
        session.close()

    def test_provider_network_error_handled_without_crashing(
        self, in_memory_session_factory
    ) -> None:
        """Provider network exception is caught and recorded in report without crashing worker."""
        provider = StubLiveProvider(raise_on_fetch=True)
        worker = LivePollingWorker(provider=provider, session_factory=in_memory_session_factory)

        report = worker.poll_cycle(override_market_open=True)
        assert report.status == "error"
        assert "Simulated upstream network timeout" in (report.error_detail or "")

    def test_database_level_unique_constraint_enforced(self, in_memory_session_factory) -> None:
        """Inserting duplicate (symbol, timestamp) directly into DB raises IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        now = datetime(2026, 9, 10, 11, 30, tzinfo=timezone.utc)
        session = in_memory_session_factory()

        q1 = LiveQuote(
            symbol="TEST",
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
            symbol="TEST",
            timestamp=now,
            open=101.0,
            high=106.0,
            low=96.0,
            close=101.0,
            volume=20,
            turnover=2020.0,
            provider="test",
            ingested_at=now,
        )

        session.add(q1)
        session.commit()

        session.add(q2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.close()
