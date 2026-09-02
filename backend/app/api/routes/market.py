from typing import Annotated

from fastapi import APIRouter, Depends

from app.models.market import (
    MarketMover,
    MarketOverview,
    MostActiveStock,
    StockQuote,
)
from app.providers.mock_market import MockMarketProvider
from app.services.market_service import MarketService


router = APIRouter(tags=["market"])
market_service = MarketService(MockMarketProvider())


def get_market_service() -> MarketService:
    return market_service


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
