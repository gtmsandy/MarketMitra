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
    def get_latest(self) -> MarketSnapshot | None:
        """Return the most recently captured snapshot, or None."""


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

    def get_latest(self) -> MarketSnapshot | None:
        return (
            self._session.query(MarketSnapshot)
            .order_by(MarketSnapshot.captured_at.desc())
            .first()
        )
