"""Unit tests for LiveMarketDataProvider interface and RestPollingLiveProvider adapter."""

import pytest
from app.providers.live_adapter import RestPollingLiveProvider
from app.providers.live_base import (
    DataFreshnessMode,
    LiveMarketDataProvider,
    MarketStatus,
)


class TestRestPollingLiveProviderContract:
    def test_unconfigured_provider_reports_inaccessible(self) -> None:
        """Provider without configured API URL reports inaccessible honestly."""
        provider = RestPollingLiveProvider(api_url=None)
        assert provider.is_live_accessible() is False
        assert provider.get_provider_name() == "unconfigured"
        assert provider.fetch_live_snapshot() is None
        assert provider.fetch_live_quotes() == []
        assert provider.fetch_intraday_history("NABIL") == []

    def test_unconfigured_provider_does_not_fabricate_live_freshness(self) -> None:
        """When live source is unconfigured, freshness is NEVER claimed as LIVE."""
        provider = RestPollingLiveProvider(api_url=None)
        mode = provider.get_data_freshness_mode()
        assert mode in (DataFreshnessMode.MARKET_CLOSED, DataFreshnessMode.DATA_UNAVAILABLE)
        assert mode != DataFreshnessMode.LIVE

    def test_circuit_breaker_trips_after_three_failures(self) -> None:
        """Provider trips circuit breaker after 3 consecutive network failures."""
        provider = RestPollingLiveProvider(
            api_url="http://127.0.0.1:19999/unreachable_nonexistent",
            provider_name="test_nepse_feed",
            timeout_seconds=0.1,
        )
        assert provider.is_live_accessible() is True

        # Simulate 3 failed polls
        for _ in range(3):
            provider.fetch_live_snapshot()

        # Circuit breaker is tripped
        assert provider.is_live_accessible() is False
        assert provider.get_market_status() == MarketStatus.DATA_UNAVAILABLE
