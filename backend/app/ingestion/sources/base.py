"""DataSource abstraction for the ingestion pipeline.

A DataSource represents where market data originates (mock, NEPSE, etc.).
It is separate from MarketDataProvider, which is the read-path abstraction
used by routes and the service layer.

DataSource is write-path only: it supplies raw, unvalidated records that
flow into the IngestionService for validation and persistence.
"""
from abc import ABC, abstractmethod

from app.ingestion.models import RawInstrumentRecord, RawPriceRecord, RawSnapshotRecord


class DataSource(ABC):
    """Abstract base for all market data ingestion sources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in logs and IngestionRun records."""

    @abstractmethod
    def fetch_instruments(self) -> list[RawInstrumentRecord]:
        """Return all instrument records available from this source."""

    @abstractmethod
    def fetch_snapshot(self) -> RawSnapshotRecord:
        """Return the current market snapshot from this source."""

    def fetch_snapshots(self) -> list[RawSnapshotRecord]:
        """Return all available market snapshot records from this source.

        Default implementation falls back to returning [self.fetch_snapshot()]
        if a snapshot is available, or an empty list.
        """
        try:
            snapshot = self.fetch_snapshot()
            return [snapshot] if snapshot is not None else []
        except Exception:
            return []
    @abstractmethod
    def fetch_prices(self, symbol: str) -> list[RawPriceRecord]:
        """Return all available price records for the given symbol."""
