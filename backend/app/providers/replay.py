"""Explicit development-only deterministic replay provider."""
from datetime import datetime, timezone
from app.providers.live_base import LiveMarketDataProvider, LiveQuoteObservation, LiveSnapshotObservation, MarketStatus, DataFreshnessMode

class DevelopmentReplayProvider(LiveMarketDataProvider):
    def __init__(self) -> None:
        self._step = 0
        self._symbols = ("NIFRA", "NABIL", "NLIC")
    def is_live_accessible(self) -> bool: return True
    def get_data_freshness_mode(self) -> DataFreshnessMode: return DataFreshnessMode.LIVE
    def get_provider_name(self) -> str: return "DEVELOPMENT_REPLAY"
    def get_market_status(self) -> MarketStatus: return MarketStatus.OPEN
    def fetch_live_snapshot(self) -> LiveSnapshotObservation:
        now = datetime.now(timezone.utc); self._step += 1
        return LiveSnapshotObservation(2000.0, 1.0, 0.05, None, None, None, MarketStatus.OPEN, now, now, self.get_provider_name())
    def fetch_live_quotes(self) -> list[LiveQuoteObservation]:
        now = datetime.now(timezone.utc)
        # deterministic sequence; event time is separate from replay capture time
        prices = {"NIFRA": 290.0, "NABIL": 520.0, "NLIC": 710.0}
        return [LiveQuoteObservation(s, p, p, p, p, 1000, p * 1000, 0.0, 0.0, now, now, self.get_provider_name()) for s, p in prices.items()]
    def fetch_intraday_history(self, symbol: str): return []
