from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import DailyPrice


@dataclass
class DailyPriceRow:
    symbol: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    turnover: float
    change: float = 0.0
    change_percent: float = 0.0
    previous_close: float = 0.0


class DailyPriceRepository(ABC):
    @abstractmethod
    def upsert_many(self, rows: list[DailyPriceRow]) -> int:
        """Insert or skip rows; returns count inserted."""

    @abstractmethod
    def get_by_symbol(self, symbol: str) -> list[DailyPrice]:
        """Return all price rows for a symbol, ordered by date ascending."""

    @abstractmethod
    def get_by_symbol_and_date_range(
        self, symbol: str, start_date: str, end_date: str
    ) -> list[DailyPrice]:
        """Return price rows for a symbol within [start_date, end_date] inclusive."""

    @abstractmethod
    def get_latest_by_symbol(self, symbol: str) -> DailyPrice | None:
        """Return the most recent price row for a symbol, or None."""


class PostgresDailyPriceRepository(DailyPriceRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_many(self, rows: list[DailyPriceRow]) -> int:
        """Insert rows, skipping any that violate the (symbol, date) unique constraint."""
        inserted = 0
        for row in rows:
            price = DailyPrice(
                symbol=row.symbol,
                date=row.date,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
                turnover=row.turnover,
                change=row.change,
                change_percent=row.change_percent,
                previous_close=row.previous_close,
            )
            self._session.add(price)
            try:
                self._session.flush()
                inserted += 1
            except IntegrityError:
                self._session.rollback()
        return inserted

    def get_by_symbol(self, symbol: str) -> list[DailyPrice]:
        return (
            self._session.query(DailyPrice)
            .filter(DailyPrice.symbol == symbol)
            .order_by(DailyPrice.date.asc())
            .all()
        )

    def get_by_symbol_and_date_range(
        self, symbol: str, start_date: str, end_date: str
    ) -> list[DailyPrice]:
        return (
            self._session.query(DailyPrice)
            .filter(
                DailyPrice.symbol == symbol,
                DailyPrice.date >= start_date,
                DailyPrice.date <= end_date,
            )
            .order_by(DailyPrice.date.asc())
            .all()
        )

    def get_latest_by_symbol(self, symbol: str) -> DailyPrice | None:
        return (
            self._session.query(DailyPrice)
            .filter(DailyPrice.symbol == symbol)
            .order_by(DailyPrice.date.desc())
            .first()
        )
