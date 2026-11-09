from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import and_, func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager

from app.db.models import DailyPrice, Instrument, LiveQuote
from app.models.market import (
    HeatmapItem,
    MarketBreadth,
    ScreenSortBy,
    ScreenSortOrder,
    SectorPerformance,
)


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
    def get_common_session_date(self, security_type: str = "EQUITY") -> str | None:
        """Return the latest date represented by the requested security type."""

    @abstractmethod
    def get_prices_for_session(self, session_date: str, security_type: str = "EQUITY") -> list[DailyPrice]:
        """Return all requested-security prices observed on one session."""
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
    def get_latest_instrument_prices(
        self, search_term: str | None = None
    ) -> list[tuple[Instrument, DailyPrice]]:
        """Return instruments joined to their latest valid price, sorted by symbol."""

    @abstractmethod
    def screen_latest_instrument_prices(
        self,
        *,
        query: str | None,
        sector: str | None,
        min_price: float | None,
        max_price: float | None,
        min_change_percent: float | None,
        max_change_percent: float | None,
        min_volume: int | None,
        min_turnover: float | None,
        page: int,
        page_size: int,
        sort_by: ScreenSortBy,
        sort_order: ScreenSortOrder,
    ) -> tuple[list[tuple[Instrument, DailyPrice]], int, str | None]:
        """Filter and paginate one common valid market session in SQL."""

    @abstractmethod
    def get_intraday_by_symbol(self, symbol: str) -> list[LiveQuote]:
        """Return all intraday live quote rows for a symbol, ordered by timestamp ascending."""

    @abstractmethod
    def get_market_breadth(self, session_date: str | None = None, security_type: str = "EQUITY") -> MarketBreadth:
        """Return advance-decline breadth metrics for the given or latest trading date."""

    @abstractmethod
    def get_sector_analytics(self, security_type: str = "EQUITY") -> list[SectorPerformance]:
        """Return aggregate sector performance, counts, and volume metrics."""

    @abstractmethod
    def get_market_heatmap(self, security_type: str = "EQUITY") -> list[HeatmapItem]:
        """Return latest equity observations for the market heatmap."""


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
                    existing.is_ohlc_valid = True
                    existing.validation_reason = None
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
                    is_ohlc_valid=True,
                )
                self._session.add(price)
                existing_map[key] = price
                result.inserted += 1

        self._session.flush()
        return result

    def get_by_symbol(self, symbol: str) -> list[DailyPrice]:
        return (
            self._session.query(DailyPrice)
            .filter(DailyPrice.symbol == symbol, DailyPrice.is_ohlc_valid.is_(True))
            .order_by(DailyPrice.date.asc())
            .all()
        )

    def get_common_session_date(self, security_type: str = "EQUITY") -> str | None:
        return self._session.execute(
            text("""SELECT max(p.date) FROM daily_prices p
                   JOIN instruments i ON i.symbol = p.symbol
                   WHERE i.security_type = :st AND p.is_ohlc_valid = true"""), {"st": security_type}
        ).scalar()

    def get_prices_for_session(self, session_date: str, security_type: str = "EQUITY") -> list[DailyPrice]:
        return (self._session.query(DailyPrice)
                .join(DailyPrice.instrument)
                .options(contains_eager(DailyPrice.instrument))
                .filter(DailyPrice.date == session_date, Instrument.security_type == security_type, DailyPrice.is_ohlc_valid.is_(True))
                .order_by(DailyPrice.turnover.desc(), DailyPrice.symbol.asc()).all())

    def get_by_symbol_and_date_range(
        self, symbol: str, start_date: str, end_date: str
    ) -> list[DailyPrice]:
        return (
            self._session.query(DailyPrice)
            .filter(
                DailyPrice.symbol == symbol,
                DailyPrice.date >= start_date,
                DailyPrice.date <= end_date,
                DailyPrice.is_ohlc_valid.is_(True),
            )
            .order_by(DailyPrice.date.asc())
            .all()
        )

    def get_latest_by_symbol(self, symbol: str) -> DailyPrice | None:
        return (
            self._session.query(DailyPrice)
            .filter(DailyPrice.symbol == symbol, DailyPrice.is_ohlc_valid.is_(True))
            .order_by(DailyPrice.date.desc())
            .first()
        )

    def get_latest_instrument_prices(
        self, search_term: str | None = None
    ) -> list[tuple[Instrument, DailyPrice]]:
        latest_valid_dates = (
            self._session.query(
                DailyPrice.symbol.label("symbol"),
                func.max(DailyPrice.date).label("date"),
            )
            .filter(DailyPrice.is_ohlc_valid.is_(True))
            .group_by(DailyPrice.symbol)
            .subquery()
        )
        query = (
            self._session.query(Instrument, DailyPrice)
            .join(latest_valid_dates, latest_valid_dates.c.symbol == Instrument.symbol)
            .join(
                DailyPrice,
                and_(
                    DailyPrice.symbol == latest_valid_dates.c.symbol,
                    DailyPrice.date == latest_valid_dates.c.date,
                    DailyPrice.is_ohlc_valid.is_(True),
                ),
            )
        )
        if search_term:
            term = search_term.lower()
            query = query.filter(
                or_(
                    func.lower(Instrument.symbol).contains(term, autoescape=True),
                    func.lower(Instrument.company_name).contains(
                        term, autoescape=True
                    ),
                )
            )
        return query.order_by(Instrument.symbol.asc()).all()

    def screen_latest_instrument_prices(
        self,
        *,
        query: str | None,
        sector: str | None,
        min_price: float | None,
        max_price: float | None,
        min_change_percent: float | None,
        max_change_percent: float | None,
        min_volume: int | None,
        min_turnover: float | None,
        page: int,
        page_size: int,
        sort_by: ScreenSortBy,
        sort_order: ScreenSortOrder,
    ) -> tuple[list[tuple[Instrument, DailyPrice]], int, str | None]:
        session_date = self.get_common_session_date("EQUITY")
        if session_date is None:
            return [], 0, None

        statement = (
            self._session.query(Instrument, DailyPrice)
            .join(DailyPrice, DailyPrice.symbol == Instrument.symbol)
            .filter(
                Instrument.security_type == "EQUITY",
                DailyPrice.date == session_date,
                DailyPrice.is_ohlc_valid.is_(True),
            )
        )
        if query:
            term = query.strip().lower()
            statement = statement.filter(
                or_(
                    func.lower(Instrument.symbol).contains(term, autoescape=True),
                    func.lower(Instrument.company_name).contains(term, autoescape=True),
                )
            )
        if sector:
            statement = statement.filter(func.lower(Instrument.sector) == sector.strip().lower())
        if min_price is not None:
            statement = statement.filter(DailyPrice.close >= min_price)
        if max_price is not None:
            statement = statement.filter(DailyPrice.close <= max_price)
        if min_change_percent is not None:
            statement = statement.filter(DailyPrice.change_percent >= min_change_percent)
        if max_change_percent is not None:
            statement = statement.filter(DailyPrice.change_percent <= max_change_percent)
        if min_volume is not None:
            statement = statement.filter(DailyPrice.volume >= min_volume)
        if min_turnover is not None:
            statement = statement.filter(DailyPrice.turnover >= min_turnover)

        total = statement.order_by(None).count()
        sort_column = {
            "symbol": Instrument.symbol,
            "price": DailyPrice.close,
            "change_percent": DailyPrice.change_percent,
            "volume": DailyPrice.volume,
            "turnover": DailyPrice.turnover,
        }[sort_by]
        primary = (
            sort_column.desc().nullslast()
            if sort_order == "desc"
            else sort_column.asc().nullslast()
        )
        rows = (
            statement.order_by(primary, Instrument.symbol.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return rows, total, session_date

    def get_intraday_by_symbol(self, symbol: str) -> list[LiveQuote]:
        return (
            self._session.query(LiveQuote)
            .filter(LiveQuote.symbol == symbol)
            .order_by(LiveQuote.timestamp.asc())
            .all()
        )

    def get_market_breadth(self, session_date: str | None = None, security_type: str = "EQUITY") -> MarketBreadth:
        target_date = session_date
        if not target_date:
            target_date = self.get_common_session_date(security_type)

        if not target_date:
            return MarketBreadth(
                observation_date="N/A",
                advancing_count=0,
                declining_count=0,
                unchanged_count=0,
                total_count=0,
                advance_decline_ratio=None,
                advancing_percent=0.0,
                declining_percent=0.0,
                unchanged_percent=0.0,
            )

        row = self._session.execute(
            text("""
                SELECT
                    count(*) as total,
                    sum(CASE WHEN p.change_percent > 0 THEN 1 ELSE 0 END) as advancing,
                    sum(CASE WHEN p.change_percent < 0 THEN 1 ELSE 0 END) as declining,
                    sum(CASE WHEN p.change_percent = 0 THEN 1 ELSE 0 END) as unchanged
                FROM daily_prices p
                JOIN instruments i ON p.symbol = i.symbol
                WHERE p.date = :dt AND i.security_type = :st AND p.is_ohlc_valid = true;
            """),
            {"dt": target_date, "st": security_type},
        ).fetchone()

        total = int(row[0]) if row and row[0] is not None else 0
        adv = int(row[1]) if row and row[1] is not None else 0
        dec = int(row[2]) if row and row[2] is not None else 0
        unc = int(row[3]) if row and row[3] is not None else 0

        adv_pct = round((adv / total) * 100, 2) if total > 0 else 0.0
        dec_pct = round((dec / total) * 100, 2) if total > 0 else 0.0
        unc_pct = round((unc / total) * 100, 2) if total > 0 else 0.0
        ratio = round(adv / dec, 2) if dec > 0 else None

        return MarketBreadth(
            observation_date=str(target_date),
            advancing_count=adv,
            declining_count=dec,
            unchanged_count=unc,
            total_count=total,
            advance_decline_ratio=ratio,
            advancing_percent=adv_pct,
            declining_percent=dec_pct,
            unchanged_percent=unc_pct,
        )

    def get_sector_analytics(self, security_type: str = "EQUITY") -> list[SectorPerformance]:
        rows = self._session.execute(
            text("""
                WITH common_session AS (SELECT max(p.date) AS date FROM daily_prices p JOIN instruments i ON i.symbol=p.symbol WHERE i.security_type=:st AND p.is_ohlc_valid = true)
                SELECT
                    i.sector as sector_name,
                    count(*) as stock_count,
                    sum(CASE WHEN p.change_percent > 0 THEN 1 ELSE 0 END) as advancing,
                    sum(CASE WHEN p.change_percent < 0 THEN 1 ELSE 0 END) as declining,
                    sum(CASE WHEN p.change_percent = 0 THEN 1 ELSE 0 END) as unchanged,
                    avg(p.change_percent) as avg_pct_change,
                    sum(p.volume) as total_volume,
                    sum(p.turnover) as total_turnover,
                    max(p.date) as latest_date
                FROM instruments i JOIN daily_prices p ON i.symbol = p.symbol
                WHERE i.security_type = :st AND i.sector IS NOT NULL AND p.is_ohlc_valid = true AND p.date=(SELECT date FROM common_session)
                GROUP BY i.sector
                ORDER BY avg_pct_change DESC;
            """),
            {"st": security_type},
        ).fetchall()

        sectors: list[SectorPerformance] = []
        for r in rows:
            sectors.append(
                SectorPerformance(
                    sector=str(r[0]),
                    stock_count=int(r[1]),
                    advancing_count=int(r[2] or 0),
                    declining_count=int(r[3] or 0),
                    unchanged_count=int(r[4] or 0),
                    average_change_percent=round(float(r[5] or 0.0), 2),
                    total_volume=int(r[6] or 0),
                    total_turnover=round(float(r[7] or 0.0), 2),
                    observation_date=str(r[8] or "N/A"),
                )
            )
        return sectors

    def get_market_heatmap(self, security_type: str = "EQUITY") -> list[HeatmapItem]:
        rows = self._session.execute(
            text("""
                WITH common_session AS (SELECT max(p.date) AS date FROM daily_prices p JOIN instruments i ON i.symbol=p.symbol WHERE i.security_type=:st AND p.is_ohlc_valid = true)
                SELECT
                    i.symbol,
                    i.company_name,
                    i.sector,
                    p.close,
                    p.change,
                    p.change_percent,
                    p.volume,
                    p.turnover,
                    p.date
                FROM instruments i JOIN daily_prices p ON i.symbol = p.symbol
                WHERE i.security_type = :st AND p.is_ohlc_valid = true AND p.date=(SELECT date FROM common_session)
                ORDER BY p.turnover DESC;
            """),
            {"st": security_type},
        ).fetchall()

        items: list[HeatmapItem] = []
        for r in rows:
            items.append(
                HeatmapItem(
                    symbol=str(r[0]),
                    company_name=str(r[1]),
                    sector=str(r[2]) if r[2] else None,
                    ltp=float(r[3]),
                    change=float(r[4]),
                    change_percent=float(r[5]),
                    volume=int(r[6]),
                    turnover=float(r[7]),
                    observation_date=str(r[8]),
                )
            )
        return items
