from datetime import datetime

from pydantic import BaseModel


class PriceHistoryPoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


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
