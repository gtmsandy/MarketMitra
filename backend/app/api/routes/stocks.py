from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.models.stock import PriceHistoryPoint, StockDetail
from app.providers.mock_market import MockMarketProvider
from app.services.market_service import MarketService


router = APIRouter(tags=["stocks"])
market_service = MarketService(MockMarketProvider())


def get_market_service() -> MarketService:
    return market_service


MarketServiceDependency = Annotated[MarketService, Depends(get_market_service)]


@router.get("/stocks/{symbol}", response_model=StockDetail)
def get_stock_detail(symbol: str, service: MarketServiceDependency) -> StockDetail:
    detail = service.get_stock_detail(symbol)
    if detail is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return detail


@router.get("/stocks/{symbol}/history", response_model=list[PriceHistoryPoint])
def get_stock_history(
    symbol: str,
    service: MarketServiceDependency,
) -> list[PriceHistoryPoint]:
    history = service.get_stock_history(symbol)
    if history is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return history
