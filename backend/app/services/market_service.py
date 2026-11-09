from app.models.market import (
    HeatmapItem,
    MarketBreadth,
    MarketMover,
    MarketOverview,
    MostActiveStock,
    SectorPerformance,
    StockQuote,
    StockScreenerResponse,
    ScreenSortBy,
    ScreenSortOrder,
)
from app.models.stock import IntradayPricePoint, PriceHistoryPoint, StockDetail
from app.providers.base import MarketDataProvider
from app.services.live_state import live_state_store
from app.core.config import is_live_market_enabled


class MarketService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self._provider = provider

    def get_market_overview(self) -> MarketOverview:
        return self._provider.get_market_overview()

    def get_top_gainers(self) -> list[MarketMover]:
        live = live_state_store.snapshot().quotes
        if live and is_live_market_enabled():
            names = {x.symbol: x.company_name for x in self._provider.get_stocks()}
            rows = [MarketMover(symbol=s, company_name=names.get(s,s), ltp=q.ltp, change_percent=q.change_percent, volume=q.volume or 0, observation_date=None) for s,q in live.items() if q.ltp is not None and q.change_percent is not None]
            return sorted(rows, key=lambda x:x.change_percent, reverse=True)[:10]
        return self._provider.get_top_gainers()

    def get_top_losers(self) -> list[MarketMover]:
        live = live_state_store.snapshot().quotes
        if live and is_live_market_enabled():
            names = {x.symbol: x.company_name for x in self._provider.get_stocks()}
            rows = [MarketMover(symbol=s, company_name=names.get(s,s), ltp=q.ltp, change_percent=q.change_percent, volume=q.volume or 0, observation_date=None) for s,q in live.items() if q.ltp is not None and q.change_percent is not None]
            return sorted(rows, key=lambda x:x.change_percent)[:10]
        return self._provider.get_top_losers()

    def get_most_active(self) -> list[MostActiveStock]:
        live = live_state_store.snapshot().quotes
        if live and is_live_market_enabled():
            names = {x.symbol: x.company_name for x in self._provider.get_stocks()}
            rows = [MostActiveStock(symbol=s, company_name=names.get(s,s), ltp=q.ltp, volume=q.volume, turnover=q.turnover or 0, observation_date=None) for s,q in live.items() if q.ltp is not None and q.volume is not None]
            return sorted(rows, key=lambda x:(x.turnover,x.volume), reverse=True)[:10]
        return self._provider.get_most_active()

    def get_stocks(self) -> list[StockQuote]:
        return self._provider.get_stocks()

    def search_stocks(self, query: str) -> list[StockQuote]:
        return self._provider.search_stocks(query)

    def screen_stocks(
        self,
        *,
        q: str | None,
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
        return self._provider.screen_stocks(
            query=q,
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

    def get_stock_detail(self, symbol: str) -> StockDetail | None:
        detail = self._provider.get_stock_detail(symbol)
        quote = live_state_store.snapshot().quotes.get(symbol.upper())
        if detail and quote and quote.ltp is not None:
            return detail.model_copy(update={"ltp": quote.ltp, "open": quote.open, "high": quote.high, "low": quote.low, "change": quote.change or 0, "change_percent": quote.change_percent or 0, "volume": quote.volume or 0, "last_updated": quote.provider_timestamp or detail.last_updated})
        return detail

    def get_stock_history(self, symbol: str) -> list[PriceHistoryPoint] | None:
        return self._provider.get_stock_history(symbol)

    def get_stock_intraday(self, symbol: str) -> list[IntradayPricePoint] | None:
        return self._provider.get_stock_intraday(symbol)

    def get_market_breadth(self) -> MarketBreadth:
        live = live_state_store.snapshot().quotes
        if live and is_live_market_enabled():
            a=sum((q.change_percent or 0)>0 for q in live.values()); d=sum((q.change_percent or 0)<0 for q in live.values()); u=len(live)-a-d; total=len(live)
            return MarketBreadth(observation_date="CURRENT", advancing_count=a, declining_count=d, unchanged_count=u, total_count=total, advance_decline_ratio=(a/d if d else None), advancing_percent=a*100/total if total else 0, declining_percent=d*100/total if total else 0, unchanged_percent=u*100/total if total else 0)
        return self._provider.get_market_breadth()

    def get_sector_analytics(self) -> list[SectorPerformance]:
        live = live_state_store.snapshot().quotes
        if live and is_live_market_enabled():
            # Reuse provider taxonomy while calculating only from currently quoted symbols.
            historical = self._provider.get_sector_analytics()
            heatmap = self._provider.get_market_heatmap()
            sector_by_symbol = {x.symbol: x.sector for x in heatmap if x.sector}
            grouped: dict[str, list] = {}
            for symbol, quote in live.items():
                sector = sector_by_symbol.get(symbol)
                if sector and quote.change_percent is not None:
                    grouped.setdefault(sector, []).append(quote)
            if grouped:
                out=[]
                for sector, quotes in grouped.items():
                    a=sum((q.change_percent or 0)>0 for q in quotes); d=sum((q.change_percent or 0)<0 for q in quotes); u=len(quotes)-a-d
                    out.append(SectorPerformance(sector=sector, stock_count=len(quotes), advancing_count=a, declining_count=d, unchanged_count=u, average_change_percent=sum(q.change_percent or 0 for q in quotes)/len(quotes), total_volume=sum(q.volume or 0 for q in quotes), total_turnover=sum(q.turnover or 0 for q in quotes), observation_date="CURRENT", methodology="equal_weighted_current_live_quotes"))
                return out
        return self._provider.get_sector_analytics()

    def get_market_heatmap(self) -> list[HeatmapItem]:
        live = live_state_store.snapshot().quotes
        if live and is_live_market_enabled():
            base = self._provider.get_market_heatmap()
            rows=[]
            for item in base:
                q=live.get(item.symbol)
                if q and q.ltp is not None and q.change is not None and q.change_percent is not None:
                    rows.append(item.model_copy(update={"ltp":q.ltp, "change":q.change, "change_percent":q.change_percent, "volume":q.volume or 0, "turnover":q.turnover or 0, "observation_date":"CURRENT"}))
            return rows
        return self._provider.get_market_heatmap()

