"""Concrete live market data adapter for external REST / WebSocket feeds.

Handles external connection boundaries, API authentication, rate limits,
error circuit breaking, and honest reporting of live data availability.
Never fabricates synthetic prices or silently returns mock data in production.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.core.market_schedule import is_market_open, KATHMANDU_TZ
from app.models.stock import PriceHistoryPoint
from app.providers.live_base import (
    DataFreshnessMode,
    LiveMarketDataProvider,
    LiveQuoteObservation,
    LiveSnapshotObservation,
    MarketStatus,
)

logger = logging.getLogger(__name__)


class RestPollingLiveProvider(LiveMarketDataProvider):
    """Production live adapter that polls an authorized external NEPSE provider feed.

    Configured via environment variables:
      NEPSE_LIVE_API_URL: Base URL of the authorized provider (e.g., NEPSE MDP or aggregator)
      NEPSE_LIVE_API_KEY: Secret authentication key / bearer token
      NEPSE_PROVIDER_NAME: Identifies the upstream provider (default: 'unconfigured')
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        provider_name: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self._api_url = api_url or os.environ.get("NEPSE_LIVE_API_URL")
        self._api_key = api_key or os.environ.get("NEPSE_LIVE_API_KEY")
        self._provider_name = (
            provider_name or os.environ.get("NEPSE_PROVIDER_NAME") or "unconfigured"
        )
        self._timeout_seconds = timeout_seconds
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._last_successful_poll: datetime | None = None

    def is_live_accessible(self) -> bool:
        """True only if an API URL is configured and circuit breaker has not tripped."""
        if not self._api_url:
            return False
        if self._consecutive_failures >= self._max_consecutive_failures:
            return False
        return True

    def get_provider_name(self) -> str:
        return self._provider_name

    def get_market_status(self) -> MarketStatus:
        """Evaluate session status based on live feed connectivity and market schedule."""
        if self._consecutive_failures >= self._max_consecutive_failures:
            return MarketStatus.DATA_UNAVAILABLE

        # Check market schedule (Sun-Thu, 11:00-15:00 Asia/Kathmandu)
        if not is_market_open():
            return MarketStatus.CLOSED

        if not self.is_live_accessible():
            return MarketStatus.DATA_UNAVAILABLE

        return MarketStatus.OPEN

    def get_data_freshness_mode(self) -> DataFreshnessMode:
        """Classify current data state honestly."""
        if not self.is_live_accessible():
            return (
                DataFreshnessMode.MARKET_CLOSED
                if not is_market_open()
                else DataFreshnessMode.DATA_UNAVAILABLE
            )

        if self._last_successful_poll is not None:
            age_seconds = (datetime.now(tz=timezone.utc) - self._last_successful_poll).total_seconds()
            if age_seconds > 120.0:
                return DataFreshnessMode.STALE
            if age_seconds > 15.0:
                return DataFreshnessMode.DELAYED
            return DataFreshnessMode.LIVE

        return DataFreshnessMode.DATA_UNAVAILABLE

    def fetch_live_snapshot(self) -> LiveSnapshotObservation | None:
        """Fetch current live snapshot from external feed. Returns None if unconfigured."""
        if not self.is_live_accessible():
            return None

        # When real credentials are provided in deployment, this performs an authenticated GET
        try:
            import httpx
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            response = httpx.get(
                f"{self._api_url}/market/snapshot",
                headers=headers,
                timeout=self._timeout_seconds,
            )
            if response.status_code == 200:
                data = response.json()
                self._consecutive_failures = 0
                self._last_successful_poll = datetime.now(tz=timezone.utc)
                return LiveSnapshotObservation(
                    nepse_index=float(data["nepse_index"]),
                    index_change=float(data.get("index_change", 0.0)),
                    index_change_percent=float(data.get("index_change_percent", 0.0)),
                    turnover=float(data["turnover"]) if data.get("turnover") is not None else None,
                    total_volume=int(data["total_volume"]) if data.get("total_volume") is not None else None,
                    total_transactions=int(data["total_transactions"]) if data.get("total_transactions") is not None else None,
                    market_status=MarketStatus.OPEN if is_market_open() else MarketStatus.CLOSED,
                    source_timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
                    captured_at=self._last_successful_poll,
                    provider=self._provider_name,
                )
            else:
                self._record_failure()
                return None
        except Exception as exc:
            logger.warning("Live snapshot poll failed from %s: %s", self._provider_name, exc)
            self._record_failure()
            return None

    def fetch_live_quotes(self) -> list[LiveQuoteObservation]:
        """Fetch live ticker quotes for all active securities."""
        if not self.is_live_accessible():
            return []

        try:
            import httpx
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            response = httpx.get(
                f"{self._api_url}/stocks/quotes",
                headers=headers,
                timeout=self._timeout_seconds,
            )
            if response.status_code == 200:
                self._consecutive_failures = 0
                self._last_successful_poll = datetime.now(tz=timezone.utc)
                quotes = []
                for item in response.json():
                    quotes.append(
                        LiveQuoteObservation(
                            symbol=str(item["symbol"]).strip().upper(),
                            ltp=float(item["ltp"]),
                            open=float(item.get("open", item["ltp"])),
                            high=float(item.get("high", item["ltp"])),
                            low=float(item.get("low", item["ltp"])),
                            volume=int(item.get("volume", 0)),
                            turnover=float(item.get("turnover", 0.0)),
                            change=float(item.get("change", 0.0)),
                            change_percent=float(item.get("change_percent", 0.0)),
                            source_timestamp=datetime.fromisoformat(item["timestamp"]) if item.get("timestamp") else None,
                            captured_at=self._last_successful_poll,
                            provider=self._provider_name,
                        )
                    )
                return quotes
            else:
                self._record_failure()
                return []
        except Exception as exc:
            logger.warning("Live quotes poll failed from %s: %s", self._provider_name, exc)
            self._record_failure()
            return []

    def fetch_intraday_history(self, symbol: str) -> list[PriceHistoryPoint]:
        """Fetch 1-minute / 5-minute intraday observations for today's session."""
        if not self.is_live_accessible():
            return []

        try:
            import httpx
            headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
            response = httpx.get(
                f"{self._api_url}/stocks/{symbol}/intraday",
                headers=headers,
                timeout=self._timeout_seconds,
            )
            if response.status_code == 200:
                self._consecutive_failures = 0
                return [
                    PriceHistoryPoint(
                        date=p["timestamp"],
                        open=float(p["open"]),
                        high=float(p["high"]),
                        low=float(p["low"]),
                        close=float(p["close"]),
                        volume=int(p.get("volume", 0)),
                    )
                    for p in response.json()
                ]
            else:
                self._record_failure()
                return []
        except Exception as exc:
            logger.warning("Intraday history poll failed for %s: %s", symbol, exc)
            self._record_failure()
            return []

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._max_consecutive_failures:
            logger.error("Live provider %s circuit breaker tripped (3 failures)", self._provider_name)
