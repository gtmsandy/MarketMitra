from abc import ABC, abstractmethod

from app.models.market import (
    HeatmapItem,
    MarketBreadth,
    MarketMover,
    MarketOverview,
    MostActiveStock,
    SectorPerformance,
    StockQuote,
)
from app.models.stock import IntradayPricePoint, PriceHistoryPoint, StockDetail


class MarketDataProvider(ABC):
    @abstractmethod
    def get_market_overview(self) -> MarketOverview:
        """Return the current normalized market overview."""

    @abstractmethod
    def get_top_gainers(self) -> list[MarketMover]:
        """Return movers sorted by percentage change, highest first."""

    @abstractmethod
    def get_top_losers(self) -> list[MarketMover]:
        """Return movers sorted by percentage change, lowest first."""

    @abstractmethod
    def get_most_active(self) -> list[MostActiveStock]:
        """Return stocks sorted by turnover, highest first."""

    @abstractmethod
    def get_stocks(self) -> list[StockQuote]:
        """Return normalized stock quotes."""

    @abstractmethod
    def search_stocks(self, query: str) -> list[StockQuote]:
        """Return stocks matching query by symbol or company name."""

    @abstractmethod
    def get_stock_detail(self, symbol: str) -> StockDetail | None:
        """Return detail for a single stock, or None if not found."""

    @abstractmethod
    def get_stock_history(self, symbol: str) -> list[PriceHistoryPoint] | None:
        """Return historical price data for a stock, or None if not found."""

    @abstractmethod
    def get_stock_intraday(self, symbol: str) -> list[IntradayPricePoint] | None:
        """Return chronological intraday price observations for a stock, or None if not found."""

    @abstractmethod
    def get_market_breadth(self) -> MarketBreadth:
        """Return the market-wide advance-decline breadth metrics."""

    @abstractmethod
    def get_sector_analytics(self) -> list[SectorPerformance]:
        """Return aggregate performance and breadth by sector."""

    @abstractmethod
    def get_market_heatmap(self) -> list[HeatmapItem]:
        """Return equity items formatted for the market heatmap."""
