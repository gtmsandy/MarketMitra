from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import DailyPrice, LiveQuote


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


@dataclass
class UpsertResult:
    inserted: int = 0
    skipped: int = 0
    replaced: int = 0


class DailyPriceRepository(ABC):
    @abstractmethod
    def upsert_many(
        self,
        rows: list[DailyPriceRow],
        on_conflict: Literal["skip", "replace"] = "skip",
    ) -> UpsertResult:
        """Insert rows.

        on_conflict="skip"    — silently skip rows that already exist (default).
        on_conflict="replace" — overwrite existing rows with new values.
        Returns an UpsertResult with per-outcome counts.
        """

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

    @abstractmethod
    def get_intraday_by_symbol(self, symbol: str) -> list[LiveQuote]:
        """Return all intraday live quote rows for a symbol, ordered by timestamp ascending."""


class PostgresDailyPriceRepository(DailyPriceRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_many(
        self,
        rows: list[DailyPriceRow],
        on_conflict: Literal["skip", "replace"] = "skip",
    ) -> UpsertResult:
        result = UpsertResult()
        if not rows:
            return result

        # Optimization: batch-load existing records for involved symbols in one query
        symbols = set(r.symbol for r in rows)
        existing_records = (
            self._session.query(DailyPrice)
            .filter(DailyPrice.symbol.in_(symbols))
            .all()
        )
        existing_map = {(p.symbol, p.date): p for p in existing_records}

        for row in rows:
            key = (row.symbol, row.date)
            existing = existing_map.get(key)
            if existing is not None:
                if on_conflict == "replace":
                    existing.open = row.open
                    existing.high = row.high
                    existing.low = row.low
                    existing.close = row.close
                    existing.volume = row.volume
                    existing.turnover = row.turnover
                    existing.change = row.change
                    existing.change_percent = row.change_percent
                    existing.previous_close = row.previous_close
                    result.replaced += 1
                else:
                    result.skipped += 1
            else:
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
                existing_map[key] = price
                result.inserted += 1

        self._session.flush()
        return result

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

    def get_intraday_by_symbol(self, symbol: str) -> list[LiveQuote]:
        return (
            self._session.query(LiveQuote)
            .filter(LiveQuote.symbol == symbol)
            .order_by(LiveQuote.timestamp.asc())
            .all()
        )
