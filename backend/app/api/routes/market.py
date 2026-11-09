from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator

from app.api.dependencies import get_market_service
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
from app.services.market_service import MarketService


router = APIRouter(tags=["market"])

MarketServiceDependency = Annotated[MarketService, Depends(get_market_service)]


class StockScreenerQuery(BaseModel):
    q: str | None = Field(default=None, max_length=80)
    sector: str | None = Field(default=None, max_length=80)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    min_change_percent: float | None = Field(default=None, ge=-100, le=1000)
    max_change_percent: float | None = Field(default=None, ge=-100, le=1000)
    min_volume: int | None = Field(default=None, ge=0)
    min_turnover: float | None = Field(default=None, ge=0)
    page: int = Field(default=1, ge=1, le=100_000)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: ScreenSortBy = "symbol"
    sort_order: ScreenSortOrder = "asc"

    @model_validator(mode="after")
    def validate_ranges(self) -> "StockScreenerQuery":
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price must be less than or equal to max_price")
        if (
            self.min_change_percent is not None
            and self.max_change_percent is not None
            and self.min_change_percent > self.max_change_percent
        ):
            raise ValueError("min_change_percent must be less than or equal to max_change_percent")
        return self


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


@router.get("/stocks/screener", response_model=StockScreenerResponse)
def screen_stocks(
    service: MarketServiceDependency,
    params: Annotated[StockScreenerQuery, Query()],
) -> StockScreenerResponse:
    return service.screen_stocks(**params.model_dump())


@router.get("/market/breadth", response_model=MarketBreadth)
def get_market_breadth(service: MarketServiceDependency) -> MarketBreadth:
    return service.get_market_breadth()


@router.get("/market/sectors", response_model=list[SectorPerformance])
def get_sector_analytics(service: MarketServiceDependency) -> list[SectorPerformance]:
    return service.get_sector_analytics()


@router.get("/market/heatmap", response_model=list[HeatmapItem])
def get_market_heatmap(service: MarketServiceDependency) -> list[HeatmapItem]:
    return service.get_market_heatmap()
