from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.market import (
    HeatmapItem,
    MarketBreadth,
    MarketMover,
    MarketOverview,
    MostActiveStock,
    SectorPerformance,
    StockQuote,
    StockScreenerItem,
    StockScreenerResponse,
    ScreenSortBy,
    ScreenSortOrder,
)
from app.models.stock import IntradayPricePoint, PriceHistoryPoint, StockDetail
from app.providers.base import MarketDataProvider
from app.core.config import is_live_market_enabled
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
            observation_date=snapshot.captured_at.date().isoformat(),
            data_freshness="HISTORICAL",
        )

    # ------------------------------------------------------------------
    # Rankings
    # ------------------------------------------------------------------

    def get_top_gainers(self) -> list[MarketMover]:
        session_date = self._prices.get_common_session_date()
        latest_prices = self._prices.get_prices_for_session(session_date) if session_date else []
        gainers = [p for p in latest_prices if p.change_percent > 0]
        gainers.sort(key=lambda p: p.change_percent, reverse=True)
        return [self._to_market_mover(p) for p in gainers]

    def get_top_losers(self) -> list[MarketMover]:
        session_date = self._prices.get_common_session_date()
        latest_prices = self._prices.get_prices_for_session(session_date) if session_date else []
        losers = [p for p in latest_prices if p.change_percent < 0]
        losers.sort(key=lambda p: p.change_percent)
        return [self._to_market_mover(p) for p in losers]

    def get_most_active(self) -> list[MostActiveStock]:
        session_date = self._prices.get_common_session_date()
        latest_prices = self._prices.get_prices_for_session(session_date) if session_date else []
        active = sorted(latest_prices, key=lambda p: p.turnover, reverse=True)
        result = []
        for price in active:
            instrument = price.instrument
            result.append(MostActiveStock(
                symbol=instrument.symbol,
                company_name=instrument.company_name,
                ltp=price.close,
                volume=price.volume,
                turnover=price.turnover,
                observation_date=price.date,
            ))
        return result

    # ------------------------------------------------------------------
    # Stock listings
    # ------------------------------------------------------------------

    def get_stocks(self) -> list[StockQuote]:
        return self._get_stock_quotes()

    def _get_stock_quotes(self, search_term: str | None = None) -> list[StockQuote]:
        instrument_prices = self._prices.get_latest_instrument_prices(search_term)
        latest_snapshot = self._snapshots.get_latest()
        snapshot_timestamp = (
            latest_snapshot.captured_at if latest_snapshot is not None else None
        )
        return [
            self._to_stock_quote(instrument, price, snapshot_timestamp)
            for instrument, price in instrument_prices
        ]

    def search_stocks(self, query: str) -> list[StockQuote]:
        if not query or not query.strip():
            return self.get_stocks()
        term = query.strip().lower()
        return self._get_stock_quotes(term)

    def screen_stocks(
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
    ) -> StockScreenerResponse:
        rows, total, session_date = self._prices.screen_latest_instrument_prices(
            query=query,
            sector=sector,
            min_price=min_price,
            max_price=max_price,
            min_change_percent=min_change_percent,
            max_change_percent=max_change_percent,
            min_volume=min_volume,
            min_turnover=min_turnover,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return StockScreenerResponse(
            items=[
                StockScreenerItem(
                    symbol=instrument.symbol,
                    company_name=instrument.company_name,
                    sector=instrument.sector,
                    ltp=price.close,
                    change_percent=price.change_percent,
                    volume=price.volume,
                    turnover=price.turnover,
                    observation_date=price.date,
                )
                for instrument, price in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
            observation_date=session_date,
        )

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

        latest_date = date.fromisoformat(price.date)
        window_start = latest_date - timedelta(weeks=52)
        history = self._prices.get_by_symbol_and_date_range(
            symbol.upper(), window_start.isoformat(), price.date
        )
        high_52w = max((p.high for p in history), default=price.high)
        low_52w = min((p.low for p in history), default=price.low)

        latest_snapshot = self._snapshots.get_latest()
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
            stock_observation_date=price.date,
            market_snapshot_date=latest_snapshot.captured_at if latest_snapshot else None,
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

    def get_stock_intraday(self, symbol: str) -> list[IntradayPricePoint] | None:
        instrument = self._instruments.get_by_symbol(symbol.upper())
        if instrument is None:
            return None
        quotes = self._prices.get_intraday_by_symbol(symbol.upper())
        if not is_live_market_enabled():
            quotes = [q for q in quotes if q.provider != "DEVELOPMENT_REPLAY"]
        return [
            IntradayPricePoint(
                timestamp=q.timestamp,
                open=q.open,
                high=q.high,
                low=q.low,
                close=q.close,
                volume=q.volume,
                turnover=q.turnover,
                provider=q.provider,
                source_timestamp=q.source_timestamp,
            )
            for q in quotes
        ]

    def get_market_breadth(self) -> MarketBreadth:
        return self._prices.get_market_breadth(security_type="EQUITY")

    def get_sector_analytics(self) -> list[SectorPerformance]:
        return self._prices.get_sector_analytics(security_type="EQUITY")

    def get_market_heatmap(self) -> list[HeatmapItem]:
        return self._prices.get_market_heatmap(security_type="EQUITY")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_all_latest_prices(self, security_type: str | None = "EQUITY"):
        """Return the latest DailyPrice row for every instrument, optionally filtered by security_type."""
        instruments = self._instruments.get_all()
        if security_type:
            instruments = [
                i for i in instruments if getattr(i, "security_type", "EQUITY") == security_type
            ]
        prices = []
        for instrument in instruments:
            price = self._prices.get_latest_by_symbol(instrument.symbol)
            if price is not None:
                prices.append(price)
        return prices

    def _to_market_mover(self, price) -> MarketMover:
        instrument = price.instrument
        return MarketMover(
            symbol=price.symbol,
            company_name=instrument.company_name,
            ltp=price.close,
            change_percent=price.change_percent,
            volume=price.volume,
            observation_date=price.date,
        )

    @staticmethod
    def _to_stock_quote(
        instrument,
        price,
        snapshot_timestamp: datetime | None = None,
    ) -> StockQuote:
        price_date = date.fromisoformat(price.date)
        last_updated = (
            snapshot_timestamp
            if snapshot_timestamp is not None and snapshot_timestamp.date() >= price_date
            else datetime.fromisoformat(f"{price.date}T00:00:00+00:00")
        )

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
            stock_observation_date=price.date,
            market_snapshot_date=snapshot_timestamp,
            sector=instrument.sector,
            turnover=price.turnover,
        )
