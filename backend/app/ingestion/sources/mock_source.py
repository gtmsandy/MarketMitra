"""MockDataSource — ingestion source backed by MockMarketProvider.

Produces deterministic raw records for local development, seeding, and
testing.  Uses the same SHA-256-seeded price history as MockMarketProvider
so results are stable across process restarts.
"""
from app.ingestion.models import RawInstrumentRecord, RawPriceRecord, RawSnapshotRecord
from app.ingestion.sources.base import DataSource
from app.providers.mock_market import MockMarketProvider


class MockDataSource(DataSource):
    """DataSource implementation that wraps MockMarketProvider."""

    def __init__(self) -> None:
        self._provider = MockMarketProvider()

    @property
    def name(self) -> str:
        return "mock"

    def fetch_instruments(self) -> list[RawInstrumentRecord]:
        return [
            RawInstrumentRecord(
                symbol=stock.symbol,
                company_name=stock.company_name,
            )
            for stock in self._provider.get_stocks()
        ]

    def fetch_snapshot(self) -> RawSnapshotRecord:
        overview = self._provider.get_market_overview()
        return RawSnapshotRecord(
            nepse_index=overview.nepse_index,
            index_change=overview.index_change,
            index_change_percent=overview.index_change_percent,
            turnover=overview.turnover,
            total_volume=overview.total_volume,
            total_transactions=overview.total_transactions,
            market_status=overview.market_status,
            captured_at=overview.last_updated,
        )

    def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
        history = self._provider.get_stock_history(symbol)
        if not history:
            return []

        records: list[RawPriceRecord] = []
        for i, point in enumerate(history):
            previous_close = history[i - 1].close if i > 0 else point.open
            change = round(point.close - previous_close, 4)
            change_pct = (
                round((change / previous_close) * 100, 4) if previous_close else 0.0
            )
            records.append(RawPriceRecord(
                symbol=symbol,
                date=point.date,
                open=point.open,
                high=point.high,
                low=point.low,
                close=point.close,
                volume=point.volume,
                turnover=round(point.close * point.volume, 2),
                change=change,
                change_percent=change_pct,
                previous_close=previous_close,
            ))
        return records
