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
from app.providers.base import MarketDataProvider


class MarketService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    def get_market_overview(self) -> MarketOverview:
        return self._provider.get_market_overview()

    def get_top_gainers(self) -> list[MarketMover]:
        return self._provider.get_top_gainers()

    def get_top_losers(self) -> list[MarketMover]:
        return self._provider.get_top_losers()

    def get_most_active(self) -> list[MostActiveStock]:
        return self._provider.get_most_active()

    def get_stocks(self) -> list[StockQuote]:
        return self._provider.get_stocks()

    def search_stocks(self, query: str) -> list[StockQuote]:
        return self._provider.search_stocks(query)

    def get_stock_detail(self, symbol: str) -> StockDetail | None:
        return self._provider.get_stock_detail(symbol)

    def get_stock_history(self, symbol: str) -> list[PriceHistoryPoint] | None:
        return self._provider.get_stock_history(symbol)

    def get_stock_intraday(self, symbol: str) -> list[IntradayPricePoint] | None:
        return self._provider.get_stock_intraday(symbol)

    def get_market_breadth(self) -> MarketBreadth:
        return self._provider.get_market_breadth()

    def get_sector_analytics(self) -> list[SectorPerformance]:
        return self._provider.get_sector_analytics()

    def get_market_heatmap(self) -> list[HeatmapItem]:
        return self._provider.get_market_heatmap()

