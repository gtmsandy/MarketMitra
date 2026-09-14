from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_market_service
from app.models.market import (
    HeatmapItem,
    MarketBreadth,
    MarketMover,
    MarketOverview,
    MostActiveStock,
    SectorPerformance,
    StockQuote,
)
from app.services.market_service import MarketService


router = APIRouter(tags=["market"])

MarketServiceDependency = Annotated[MarketService, Depends(get_market_service)]


@router.get("/market/overview", response_model=MarketOverview)
def get_market_overview(service: MarketServiceDependency) -> MarketOverview:
    return service.get_market_overview()


@router.get("/market/gainers", response_model=list[MarketMover])
def get_top_gainers(service: MarketServiceDependency) -> list[MarketMover]:
    return service.get_top_gainers()


@router.get("/market/losers", response_model=list[MarketMover])
def get_top_losers(service: MarketServiceDependency) -> list[MarketMover]:
    return service.get_top_losers()


@router.get("/market/most-active", response_model=list[MostActiveStock])
def get_most_active(service: MarketServiceDependency) -> list[MostActiveStock]:
    return service.get_most_active()


@router.get("/stocks", response_model=list[StockQuote])
def get_stocks(
    service: MarketServiceDependency,
    q: str | None = None,
) -> list[StockQuote]:
    if q:
        return service.search_stocks(q)
    return service.get_stocks()


@router.get("/market/breadth", response_model=MarketBreadth)
def get_market_breadth(service: MarketServiceDependency) -> MarketBreadth:
    return service.get_market_breadth()


@router.get("/market/sectors", response_model=list[SectorPerformance])
def get_sector_analytics(service: MarketServiceDependency) -> list[SectorPerformance]:
    return service.get_sector_analytics()


@router.get("/market/heatmap", response_model=list[HeatmapItem])
def get_market_heatmap(service: MarketServiceDependency) -> list[HeatmapItem]:
    return service.get_market_heatmap()
