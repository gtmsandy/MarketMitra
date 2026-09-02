from datetime import datetime

from pydantic import BaseModel


class MarketOverview(BaseModel):
    nepse_index: float
    index_change: float
    index_change_percent: float
    turnover: float
    total_volume: int
    total_transactions: int
    market_status: str
    last_updated: datetime


class StockQuote(BaseModel):
    symbol: str
    company_name: str
    ltp: float
    change: float
    change_percent: float
    open: float
    high: float
    low: float
    previous_close: float
    volume: int
    last_updated: datetime


class MarketMover(BaseModel):
    symbol: str
    company_name: str
    ltp: float
    change_percent: float
    volume: int


class MostActiveStock(BaseModel):
    symbol: str
    company_name: str
    ltp: float
    volume: int
    turnover: float
