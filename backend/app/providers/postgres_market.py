from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.market import (
    MarketMover,
    MarketOverview,
    MostActiveStock,
    StockQuote,
)
from app.models.stock import PriceHistoryPoint, StockDetail
from app.providers.base import MarketDataProvider
from app.repositories.instrument_repository import PostgresInstrumentRepository
from app.repositories.market_repository import PostgresMarketSnapshotRepository
from app.repositories.price_repository import PostgresDailyPriceRepository


class PostgresMarketProvider(MarketDataProvider):
    """Market data provider backed by the PostgreSQL repository layer.

    Receives a request-scoped SQLAlchemy Session.  Repositories are
    constructed per-request so the session lifecycle is not leaked.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._instruments = PostgresInstrumentRepository(session)
        self._snapshots = PostgresMarketSnapshotRepository(session)
        self._prices = PostgresDailyPriceRepository(session)

    # ------------------------------------------------------------------
    # Market overview
    # ------------------------------------------------------------------

    def get_market_overview(self) -> MarketOverview:
        snapshot = self._snapshots.get_latest()
        if snapshot is None:
            raise RuntimeError(
                "No market snapshot found in the database. "
                "Run the seed utility to populate initial data."
            )
        return MarketOverview(
            nepse_index=snapshot.nepse_index,
            index_change=snapshot.index_change,
            index_change_percent=snapshot.index_change_percent,
            turnover=snapshot.turnover,
            total_volume=snapshot.total_volume,
            total_transactions=snapshot.total_transactions,
            market_status=snapshot.market_status,
            last_updated=snapshot.captured_at,
        )

    # ------------------------------------------------------------------
    # Rankings
    # ------------------------------------------------------------------

    def get_top_gainers(self) -> list[MarketMover]:
        latest_prices = self._get_all_latest_prices()
        gainers = [p for p in latest_prices if p.change_percent > 0]
        gainers.sort(key=lambda p: p.change_percent, reverse=True)
        return [self._to_market_mover(p) for p in gainers]

    def get_top_losers(self) -> list[MarketMover]:
        latest_prices = self._get_all_latest_prices()
        losers = [p for p in latest_prices if p.change_percent < 0]
        losers.sort(key=lambda p: p.change_percent)
        return [self._to_market_mover(p) for p in losers]

    def get_most_active(self) -> list[MostActiveStock]:
        latest_prices = self._get_all_latest_prices()
        active = sorted(latest_prices, key=lambda p: p.turnover, reverse=True)
        result = []
        for price in active:
            instrument = self._instruments.get_by_symbol(price.symbol)
            if instrument is None:
                continue
            result.append(MostActiveStock(
                symbol=instrument.symbol,
                company_name=instrument.company_name,
                ltp=price.close,
                volume=price.volume,
                turnover=price.turnover,
            ))
        return result

    # ------------------------------------------------------------------
    # Stock listings
    # ------------------------------------------------------------------

    def get_stocks(self) -> list[StockQuote]:
        instruments = self._instruments.get_all()
        latest_snapshot = self._snapshots.get_latest()
        snapshot_timestamp = (
            latest_snapshot.captured_at if latest_snapshot is not None else None
        )
        quotes = []
        for instrument in instruments:
            price = self._prices.get_latest_by_symbol(instrument.symbol)
            if price is None:
                continue
            quotes.append(self._to_stock_quote(instrument, price, snapshot_timestamp))
        return quotes

    def search_stocks(self, query: str) -> list[StockQuote]:
        if not query or not query.strip():
            return self.get_stocks()
        term = query.strip().lower()
        all_quotes = self.get_stocks()
        return [
            q for q in all_quotes
            if term in q.symbol.lower() or term in q.company_name.lower()
        ]

    # ------------------------------------------------------------------
    # Stock detail and history
    # ------------------------------------------------------------------

    def get_stock_detail(self, symbol: str) -> StockDetail | None:
        instrument = self._instruments.get_by_symbol(symbol.upper())
        if instrument is None:
            return None
        price = self._prices.get_latest_by_symbol(symbol.upper())
        if price is None:
            return None

        history = self._prices.get_by_symbol(symbol.upper())
        high_52w = max((p.high for p in history), default=price.high)
        low_52w = min((p.low for p in history), default=price.low)
        high_52w = max(high_52w, price.high)
        low_52w = min(low_52w, price.low)

        latest_snapshot = self._snapshots.get_latest()
        if latest_snapshot is not None:
            last_updated = latest_snapshot.captured_at
        else:
            last_updated = datetime.fromisoformat(f"{price.date}T00:00:00+00:00")

        return StockDetail(
            symbol=instrument.symbol,
            company_name=instrument.company_name,
            ltp=price.close,
            change=price.change,
            change_percent=price.change_percent,
            open=price.open,
            high=price.high,
            low=price.low,
            previous_close=price.previous_close,
            volume=price.volume,
            last_updated=last_updated,
            fifty_two_week_high=round(high_52w, 2),
            fifty_two_week_low=round(low_52w, 2),
        )

    def get_stock_history(self, symbol: str) -> list[PriceHistoryPoint] | None:
        instrument = self._instruments.get_by_symbol(symbol.upper())
        if instrument is None:
            return None
        rows = self._prices.get_by_symbol(symbol.upper())
        return [
            PriceHistoryPoint(
                date=row.date,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_all_latest_prices(self):
        """Return the latest DailyPrice row for every instrument."""
        instruments = self._instruments.get_all()
        prices = []
        for instrument in instruments:
            price = self._prices.get_latest_by_symbol(instrument.symbol)
            if price is not None:
                prices.append(price)
        return prices

    def _to_market_mover(self, price) -> MarketMover:
        instrument = self._instruments.get_by_symbol(price.symbol)
        return MarketMover(
            symbol=price.symbol,
            company_name=instrument.company_name if instrument else price.symbol,
            ltp=price.close,
            change_percent=price.change_percent,
            volume=price.volume,
        )

    @staticmethod
    def _to_stock_quote(
        instrument,
        price,
        snapshot_timestamp: datetime | None = None,
    ) -> StockQuote:
        if snapshot_timestamp is not None:
            last_updated = snapshot_timestamp
        else:
            last_updated = datetime.fromisoformat(f"{price.date}T00:00:00+00:00")
        return StockQuote(
            symbol=instrument.symbol,
            company_name=instrument.company_name,
            ltp=price.close,
            change=price.change,
            change_percent=price.change_percent,
            open=price.open,
            high=price.high,
            low=price.low,
            previous_close=price.previous_close,
            volume=price.volume,
            last_updated=last_updated,
        )
