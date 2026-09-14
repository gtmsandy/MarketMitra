from datetime import datetime

from pydantic import BaseModel


class MarketOverview(BaseModel):
    nepse_index: float
    index_change: float
    index_change_percent: float
    turnover: float | None = None
    total_volume: int | None = None
    total_transactions: int | None = None
    market_status: str
    last_updated: datetime
    observation_date: str | None = None
    data_freshness: str = "HISTORICAL"


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
    stock_observation_date: str | None = None
    market_snapshot_date: datetime | None = None


class MarketMover(BaseModel):
    symbol: str
    company_name: str
    ltp: float
    change_percent: float
    volume: int
    observation_date: str | None = None


class MostActiveStock(BaseModel):
    symbol: str
    company_name: str
    ltp: float
    volume: int
    turnover: float
    observation_date: str | None = None


class MarketBreadth(BaseModel):
    observation_date: str
    advancing_count: int
    declining_count: int
    unchanged_count: int
    total_count: int
    advance_decline_ratio: float | None = None
    advancing_percent: float
    declining_percent: float
    unchanged_percent: float


class SectorPerformance(BaseModel):
    sector: str
    stock_count: int
    advancing_count: int
    declining_count: int
    unchanged_count: int
    average_change_percent: float
    total_volume: int
    total_turnover: float
    observation_date: str
    methodology: str = "equal_weighted_constituent_daily_percentage_change"


class HeatmapItem(BaseModel):
    symbol: str
    company_name: str
    sector: str | None = None
    ltp: float
    change: float
    change_percent: float
    volume: int
    turnover: float
    observation_date: str
    weight_metric: str = "turnover"
