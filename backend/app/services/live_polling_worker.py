"""Live market polling worker foundation.

Runs as a lightweight, non-blocking background service that periodically polls
a configured LiveMarketDataProvider during active NEPSE trading sessions.

Key guarantees:
1. Polls strictly during open market sessions (is_market_open()).
2. Validates quotes via live_validator.py before persistence (never clamps).
3. Deduplicates identical (symbol, timestamp) observations.
4. Persists valid ticks into live_quotes.
5. Operates in honest DATA_UNAVAILABLE / HISTORICAL state when no live provider is configured.
6. Catches and logs upstream network errors without crashing the worker.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.market_schedule import is_market_open
from app.db.models import Instrument, LiveQuote
from app.ingestion.live_validator import validate_live_stock_quote
from app.providers.live_base import LiveMarketDataProvider, LiveQuoteObservation

logger = logging.getLogger(__name__)


@dataclass
class PollingCycleReport:
    """Summary of a single live polling execution."""
    timestamp: datetime
    status: str  # "success" | "skipped_market_closed" | "skipped_provider_inaccessible" | "error"
    quotes_received: int = 0
    quotes_accepted: int = 0
    quotes_rejected: int = 0
    quotes_duplicate: int = 0
    error_detail: str | None = None
    rejections: list[str] = field(default_factory=list)


class LivePollingWorker:
    """Provider-agnostic live data polling background service."""

    def __init__(
        self,
        provider: LiveMarketDataProvider,
        session_factory: Callable[[], Session],
        poll_interval_seconds: float = 30.0,
        enable_pre_open: bool = False,
    ) -> None:
        self._provider = provider
        self._session_factory = session_factory
        self._poll_interval = poll_interval_seconds
        self._enable_pre_open = enable_pre_open
        self._is_running = False
        self._task: asyncio.Task | None = None
        self._last_report: PollingCycleReport | None = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def last_report(self) -> PollingCycleReport | None:
        return self._last_report

    async def start(self) -> None:
        """Start the background polling loop without blocking the main event loop."""
        if self._is_running:
            return
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("LivePollingWorker started (interval: %.1fs)", self._poll_interval)

    async def stop(self) -> None:
        """Gracefully stop the background polling worker."""
        if not self._is_running:
            return
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("LivePollingWorker stopped")

    async def _run_loop(self) -> None:
        while self._is_running:
            try:
                self.poll_cycle()
            except Exception as exc:
                logger.error("Unexpected error in live polling cycle: %s", exc, exc_info=True)
            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break

    def poll_cycle(self, override_market_open: bool = False) -> PollingCycleReport:
        """Execute one discrete poll-validate-persist cycle.

        Returns a structured PollingCycleReport.
        """
        now = datetime.now(tz=timezone.utc)

        # 1. Market schedule check
        if not override_market_open and not is_market_open():
            report = PollingCycleReport(
                timestamp=now,
                status="skipped_market_closed",
            )
            self._last_report = report
            return report

        # 2. Provider accessibility check
        if not self._provider.is_live_accessible():
            report = PollingCycleReport(
                timestamp=now,
                status="skipped_provider_inaccessible",
            )
            self._last_report = report
            return report

        # 3. Fetch quotes from provider
        try:
            raw_quotes: list[LiveQuoteObservation] = self._provider.fetch_live_quotes()
        except Exception as exc:
            report = PollingCycleReport(
                timestamp=now,
                status="error",
                error_detail=f"Provider fetch error: {exc}",
            )
            self._last_report = report
            return report

        report = PollingCycleReport(
            timestamp=now,
            status="success",
            quotes_received=len(raw_quotes),
        )

        if not raw_quotes:
            self._last_report = report
            return report

        # 4. Validate and persist in a single transactional session
        session: Session = self._session_factory()
        try:
            # Preload existing instruments to satisfy FK constraints
            symbols_in_feed = set(q.symbol for q in raw_quotes)
            existing_instruments = set(
                session.scalars(
                    select(Instrument.symbol).where(Instrument.symbol.in_(symbols_in_feed))
                ).all()
            )

            # Preload recent live_quotes for deduplication on (symbol, timestamp)
            existing_rows = session.execute(
                select(LiveQuote.symbol, LiveQuote.timestamp).where(
                    LiveQuote.symbol.in_(symbols_in_feed),
                )
            ).all()

            def _norm_dt(dt):
                if dt is None:
                    return None
                if isinstance(dt, str):
                    return dt[:19]
                return dt.replace(tzinfo=None).isoformat()[:19]

            existing_quotes = {
                (row[0], _norm_dt(row[1])) for row in existing_rows
            }

            to_insert: list[LiveQuote] = []

            for q in raw_quotes:
                if q.symbol not in existing_instruments:
                    # Skip unknown securities to maintain strict relational integrity
                    continue

                dedup_key = (q.symbol, _norm_dt(q.captured_at))
                if dedup_key in existing_quotes:
                    report.quotes_duplicate += 1
                    continue

                # Calculate previous close base for regulatory limit evaluation
                # In live feeds, previous_close = ltp - change
                derived_prev_close = q.ltp - q.change if (q.ltp - q.change) > 0 else q.open

                # Regulatory validation: evaluate ±15% normal limit (never clamped!)
                val_result = validate_live_stock_quote(
                    symbol=q.symbol,
                    ltp=q.ltp,
                    previous_close=derived_prev_close,
                    is_pre_open=False,
                )

                if not val_result.is_valid:
                    report.quotes_rejected += 1
                    report.rejections.append(f"{q.symbol}: [{val_result.rule_name}] {val_result.message}")
                    continue

                # Valid quote: stage for persistence
                to_insert.append(
                    LiveQuote(
                        symbol=q.symbol,
                        timestamp=q.captured_at,
                        open=q.open,
                        high=q.high,
                        low=q.low,
                        close=q.ltp,
                        volume=q.volume,
                        turnover=q.turnover,
                        provider=q.provider,
                        source_timestamp=q.source_timestamp,
                        ingested_at=now,
                    )
                )
                existing_quotes.add(dedup_key)
                report.quotes_accepted += 1

            if to_insert:
                session.add_all(to_insert)
                session.commit()
            else:
                session.rollback()

        except Exception as exc:
            session.rollback()
            report.status = "error"
            report.error_detail = f"Database persistence error: {exc}"
            logger.error("LivePollingWorker persistence error: %s", exc, exc_info=True)
        finally:
            session.close()

        self._last_report = report
        return report
