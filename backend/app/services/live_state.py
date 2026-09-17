"""Provider-independent canonical current market state."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any

@dataclass
class CanonicalQuote:
    symbol: str
    ltp: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    change: float | None = None
    change_percent: float | None = None
    volume: int | None = None
    turnover: float | None = None
    transactions: int | None = None
    provider_timestamp: datetime | None = None
    ingested_at: datetime | None = None

@dataclass
class CanonicalMarketState:
    provider: str = "unconfigured"
    provider_timestamp: datetime | None = None
    ingested_at: datetime | None = None
    market_status: str = "DATA_UNAVAILABLE"
    data_freshness: str = "DATA_UNAVAILABLE"
    index: float | None = None
    index_change: float | None = None
    index_change_percent: float | None = None
    turnover: float | None = None
    volume: int | None = None
    transactions: int | None = None
    quotes: dict[str, CanonicalQuote] = field(default_factory=dict)

class LiveStateStore:
    def __init__(self) -> None:
        self._state = CanonicalMarketState()
        self._lock = RLock()
        self._listeners: list[Any] = []

    def snapshot(self) -> CanonicalMarketState:
        with self._lock:
            return CanonicalMarketState(**{**asdict(self._state), "quotes": {k: CanonicalQuote(**asdict(v)) for k, v in self._state.quotes.items()}})

    def update_market(self, **values: Any) -> bool:
        with self._lock:
            changed = any(getattr(self._state, k) != v for k, v in values.items() if v is not None)
            for k, v in values.items():
                if v is not None:
                    setattr(self._state, k, v)
            if changed:
                self._state.ingested_at = datetime.now(timezone.utc)
        return changed

    def update_quote(self, quote: CanonicalQuote) -> bool:
        with self._lock:
            old = self._state.quotes.get(quote.symbol)
            if old is None:
                changed = True
            else:
                old_data = asdict(old); new_data = asdict(quote)
                old_data.pop("ingested_at", None); new_data.pop("ingested_at", None)
                changed = old_data != new_data
            if changed:
                quote.ingested_at = quote.ingested_at or datetime.now(timezone.utc)
                self._state.quotes[quote.symbol] = quote
        return changed

    def subscribe(self, listener: Any) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unsubscribe(self, listener: Any) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

live_state_store = LiveStateStore()
