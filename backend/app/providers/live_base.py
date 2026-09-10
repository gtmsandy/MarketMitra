"""Live market data provider interfaces and domain contracts.

Defines the clean abstraction boundary for real-time and delayed NEPSE market
feeds without coupling the core application or historical persistence layer
to any specific external vendor.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal

from app.models.market import MarketOverview, StockQuote
from app.models.stock import PriceHistoryPoint


class MarketStatus(str, Enum):
    """Trading session lifecycle status for NEPSE."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    HALTED = "HALTED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    STALE = "STALE"


class DataFreshnessMode(str, Enum):
    """Data source freshness classification presented to clients."""
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    HISTORICAL = "HISTORICAL"
    STALE = "STALE"
    MARKET_CLOSED = "MARKET_CLOSED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


@dataclass
class LiveQuoteObservation:
    """Individual real-time or intraday security price tick."""
    symbol: str
    ltp: float
    open: float
    high: float
    low: float
    volume: int
    turnover: float
    change: float
    change_percent: float
    source_timestamp: datetime | None
    captured_at: datetime
    provider: str


@dataclass
class LiveSnapshotObservation:
    """Real-time market-wide benchmark index observation."""
    nepse_index: float
    index_change: float
    index_change_percent: float
    turnover: float | None
    total_volume: int | None
    total_transactions: int | None
    market_status: MarketStatus
    source_timestamp: datetime | None
    captured_at: datetime
    provider: str


class LiveMarketDataProvider(ABC):
    """Abstract interface for real-time / streaming / delayed NEPSE market data."""

    @abstractmethod
    def is_live_accessible(self) -> bool:
        """Return True if an authorized external live feed is reachable and active."""

    @abstractmethod
    def get_data_freshness_mode(self) -> DataFreshnessMode:
        """Return the current operational freshness classification."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the identifier of the configured live data provider."""

    @abstractmethod
    def get_market_status(self) -> MarketStatus:
        """Return current live or scheduled market session status."""

    @abstractmethod
    def fetch_live_snapshot(self) -> LiveSnapshotObservation | None:
        """Fetch current live index snapshot from the provider feed, or None."""

    @abstractmethod
    def fetch_live_quotes(self) -> list[LiveQuoteObservation]:
        """Fetch latest quotes for all active securities from the provider feed."""

    @abstractmethod
    def fetch_intraday_history(self, symbol: str) -> list[PriceHistoryPoint]:
        """Fetch intraday time-series observations for a symbol during market hours."""
