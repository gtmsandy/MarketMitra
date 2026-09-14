from datetime import datetime

from pydantic import BaseModel


class PriceHistoryPoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class IntradayPricePoint(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    turnover: float = 0.0
    provider: str = "unspecified"
    source_timestamp: datetime | None = None


class StockDetail(BaseModel):
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
    fifty_two_week_high: float
    fifty_two_week_low: float
    stock_observation_date: str | None = None
    market_snapshot_date: datetime | None = None
