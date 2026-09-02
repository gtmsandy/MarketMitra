from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import MarketSnapshot


class MarketSnapshotRepository(ABC):
    @abstractmethod
    def insert(
        self,
        nepse_index: float,
        index_change: float,
        index_change_percent: float,
        turnover: float,
        total_volume: int,
        total_transactions: int,
        market_status: str,
        captured_at: datetime,
    ) -> MarketSnapshot:
        """Insert a new market snapshot."""

    @abstractmethod
    def insert_if_new_day(
        self,
        nepse_index: float,
        index_change: float,
        index_change_percent: float,
        turnover: float,
        total_volume: int,
        total_transactions: int,
        market_status: str,
        captured_at: datetime,
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
        turnover: float,
        total_volume: int,
        total_transactions: int,
        market_status: str,
        captured_at: datetime,
    ) -> MarketSnapshot:
        snapshot = MarketSnapshot(
            nepse_index=nepse_index,
            index_change=index_change,
            index_change_percent=index_change_percent,
            turnover=turnover,
            total_volume=total_volume,
            total_transactions=total_transactions,
            market_status=market_status,
            captured_at=captured_at,
        )
        self._session.add(snapshot)
        return snapshot

    def insert_if_new_day(
        self,
        nepse_index: float,
        index_change: float,
        index_change_percent: float,
        turnover: float,
        total_volume: int,
        total_transactions: int,
        market_status: str,
        captured_at: datetime,
    ) -> tuple[MarketSnapshot, bool]:
        """Insert snapshot only if the calendar date has no existing snapshot.

        Deduplication is by date string (YYYY-MM-DD) derived from captured_at.
        This prevents identical snapshots from accumulating on repeated runs
        while still allowing snapshots on different days.
        """
        date_str = captured_at.strftime("%Y-%m-%d")
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
            captured_at=captured_at,
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
        # ISO date prefix match: captured_at cast to string starts with YYYY-MM-DD.
        # Using SQLAlchemy's func.strftime for SQLite compat; on Postgres this is
        # equivalent to DATE(captured_at)::text = date_str.
        from sqlalchemy import func
        return (
            self._session.query(MarketSnapshot)
            .filter(
                func.strftime("%Y-%m-%d", MarketSnapshot.captured_at) == date_str
            )
            .first()
        )
