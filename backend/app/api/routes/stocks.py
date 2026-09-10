from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_market_service
from app.models.stock import IntradayPricePoint, PriceHistoryPoint, StockDetail
from app.services.market_service import MarketService


router = APIRouter(tags=["stocks"])

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


@router.get("/stocks/{symbol}/intraday", response_model=list[IntradayPricePoint])
def get_stock_intraday(
    symbol: str,
    service: MarketServiceDependency,
) -> list[IntradayPricePoint]:
    intraday = service.get_stock_intraday(symbol)
    if intraday is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return intraday
