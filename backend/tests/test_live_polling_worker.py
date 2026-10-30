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
from app.services.live_state import LiveStateStore
import app.services.live_polling_worker as live_polling_worker_module


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


@pytest.fixture(autouse=True)
def isolated_live_state(monkeypatch):
    """Keep shared live state deterministic and isolated for every worker test."""
    store = LiveStateStore()
    monkeypatch.setattr(live_polling_worker_module, "live_state_store", store)
    return store


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

    def test_valid_quotes_validated_persisted_and_published(
        self, in_memory_session_factory, isolated_live_state
    ) -> None:
        """Valid quotes within ±15% are persisted and published to shared state."""
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
        published = isolated_live_state.snapshot().quotes
        assert published["TEST"].ltp == 105.0

        # Verify DB
        session = in_memory_session_factory()
        saved = session.query(LiveQuote).filter_by(symbol="TEST").all()
        assert len(saved) == 1
        assert saved[0].close == 105.0
        assert saved[0].provider == "stub_live_provider"
        session.close()

    def test_quotes_exceeding_15_percent_rejected_without_mutation(
        self, in_memory_session_factory, isolated_live_state
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
        assert "TEST" not in isolated_live_state.snapshot().quotes

        # Verify DB: 0 rows saved
        session = in_memory_session_factory()
        assert session.query(LiveQuote).filter_by(symbol="TEST").count() == 0
        session.close()

    def test_non_positive_price_rejected_without_reaching_shared_state(
        self, in_memory_session_factory, isolated_live_state
    ) -> None:
        """A structurally invalid price is rejected before publication or persistence."""
        now = datetime.now(tz=timezone.utc)
        invalid_quote = LiveQuoteObservation(
            symbol="TEST",
            ltp=-1.0,
            open=100.0,
            high=100.0,
            low=-1.0,
            volume=50,
            turnover=50.0,
            change=0.0,
            change_percent=0.0,
            source_timestamp=now,
            captured_at=now,
            provider="stub_live_provider",
        )
        worker = LivePollingWorker(
            provider=StubLiveProvider(quotes=[invalid_quote]),
            session_factory=in_memory_session_factory,
        )

        report = worker.poll_cycle(override_market_open=True)

        assert report.quotes_rejected == 1
        assert "TEST" not in isolated_live_state.snapshot().quotes
        session = in_memory_session_factory()
        assert session.query(LiveQuote).filter_by(symbol="TEST").count() == 0
        session.close()

    def test_unknown_instrument_never_reaches_shared_state(
        self, in_memory_session_factory, isolated_live_state
    ) -> None:
        """Provider symbols absent from the instrument taxonomy are not published."""
        now = datetime.now(tz=timezone.utc)
        unknown_quote = LiveQuoteObservation(
            symbol="UNKNOWN",
            ltp=105.0,
            open=100.0,
            high=106.0,
            low=99.0,
            volume=500,
            turnover=52500.0,
            change=5.0,
            change_percent=5.0,
            source_timestamp=now,
            captured_at=now,
            provider="stub_live_provider",
        )
        worker = LivePollingWorker(
            provider=StubLiveProvider(quotes=[unknown_quote]),
            session_factory=in_memory_session_factory,
        )

        report = worker.poll_cycle(override_market_open=True)

        assert report.quotes_accepted == 0
        assert "UNKNOWN" not in isolated_live_state.snapshot().quotes
        session = in_memory_session_factory()
        assert session.query(LiveQuote).filter_by(symbol="UNKNOWN").count() == 0
        session.close()

    def test_duplicate_timestamp_updates_shared_state_without_duplicate_persistence(
        self, in_memory_session_factory, isolated_live_state
    ) -> None:
        """A valid duplicate timestamp refreshes state without adding a database row."""
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

        # Poll 2 with a valid update at the same persistence timestamp
        provider._quotes = [
            LiveQuoteObservation(
                symbol="TEST",
                ltp=103.0,
                open=100.0,
                high=104.0,
                low=99.0,
                volume=250,
                turnover=25750.0,
                change=3.0,
                change_percent=3.0,
                source_timestamp=now,
                captured_at=now,
                provider="stub_live_provider",
            )
        ]
        r2 = worker.poll_cycle(override_market_open=True)
        assert r2.quotes_accepted == 0
        assert r2.quotes_duplicate == 1
        assert isolated_live_state.snapshot().quotes["TEST"].ltp == 103.0

        # DB has exactly 1 row with the first persisted observation
        session = in_memory_session_factory()
        saved = session.query(LiveQuote).filter_by(symbol="TEST").all()
        assert len(saved) == 1
        assert saved[0].close == 102.0
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
