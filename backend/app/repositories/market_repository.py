from abc import ABC, abstractmethod
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import MarketSnapshot


class MarketSnapshotRepository(ABC):
    @abstractmethod
    def insert(
        self,
        nepse_index: float,
        index_change: float,
        index_change_percent: float,
        turnover: float | None = None,
        total_volume: int | None = None,
        total_transactions: int | None = None,
        market_status: str = "CLOSED",
        captured_at: datetime | None = None,
    ) -> MarketSnapshot:
        """Insert a new market snapshot."""

    @abstractmethod
    def insert_if_new_day(
        self,
        nepse_index: float,
        index_change: float,
        index_change_percent: float,
        turnover: float | None = None,
        total_volume: int | None = None,
        total_transactions: int | None = None,
        market_status: str = "CLOSED",
        captured_at: datetime | None = None,
    ) -> tuple[MarketSnapshot, bool]:
        """Insert snapshot only if no snapshot exists for the same calendar date.

        Returns (snapshot, was_inserted).  If a snapshot for the day already
        exists, returns (existing_snapshot, False) without inserting.
        """

    @abstractmethod
    def get_latest(self) -> MarketSnapshot | None:
        """Return the most recently captured snapshot, or None."""

    @abstractmethod
    def get_by_date(self, date_str: str) -> MarketSnapshot | None:
        """Return the snapshot for a given ISO-8601 date string, or None."""


class PostgresMarketSnapshotRepository(MarketSnapshotRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert(
        self,
        nepse_index: float,
        index_change: float,
        index_change_percent: float,
        turnover: float | None = None,
        total_volume: int | None = None,
        total_transactions: int | None = None,
        market_status: str = "CLOSED",
        captured_at: datetime | None = None,
    ) -> MarketSnapshot:
        effective_captured_at = captured_at or datetime.now(tz=timezone.utc)
        snapshot = MarketSnapshot(
            nepse_index=nepse_index,
            index_change=index_change,
            index_change_percent=index_change_percent,
            turnover=turnover,
            total_volume=total_volume,
            total_transactions=total_transactions,
            market_status=market_status,
            captured_at=effective_captured_at,
        )
        self._session.add(snapshot)
        return snapshot

    def insert_if_new_day(
        self,
        nepse_index: float,
        index_change: float,
        index_change_percent: float,
        turnover: float | None = None,
        total_volume: int | None = None,
        total_transactions: int | None = None,
        market_status: str = "CLOSED",
        captured_at: datetime | None = None,
    ) -> tuple[MarketSnapshot, bool]:
        effective_captured_at = captured_at or datetime.now(tz=timezone.utc)
        date_str = effective_captured_at.strftime("%Y-%m-%d")
        existing = self.get_by_date(date_str)
        if existing is not None:
            return existing, False

        snapshot = self.insert(
            nepse_index=nepse_index,
            index_change=index_change,
            index_change_percent=index_change_percent,
            turnover=turnover,
            total_volume=total_volume,
            total_transactions=total_transactions,
            market_status=market_status,
            captured_at=effective_captured_at,
        )
        return snapshot, True

    def get_latest(self) -> MarketSnapshot | None:
        return (
            self._session.query(MarketSnapshot)
            .order_by(MarketSnapshot.captured_at.desc())
            .first()
        )

    def get_by_date(self, date_str: str) -> MarketSnapshot | None:
        """Return the first snapshot whose captured_at matches the given date string."""
        target_date = date.fromisoformat(date_str)
        start_dt = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        end_dt = start_dt + timedelta(days=1)
        return (
            self._session.query(MarketSnapshot)
            .filter(
                MarketSnapshot.captured_at >= start_dt,
                MarketSnapshot.captured_at < end_dt,
            )
            .first()
        )
