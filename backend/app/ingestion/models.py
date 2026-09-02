"""Domain models for the ingestion pipeline.

These types are internal to the ingestion layer.  They describe raw source
records before validation and the structured results produced after a run.
They are distinct from the API-facing Pydantic models in app.models.
"""
from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# Raw source records  (unvalidated, as received from a DataSource)
# ---------------------------------------------------------------------------

@dataclass
class RawInstrumentRecord:
    symbol: str
    company_name: str
    sector: str | None = None


@dataclass
class RawSnapshotRecord:
    nepse_index: float
    index_change: float
    index_change_percent: float
    turnover: float
    total_volume: int
    total_transactions: int
    market_status: str
    captured_at: datetime


@dataclass
class RawPriceRecord:
    symbol: str
    date: str          # expected ISO-8601: YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: int
    turnover: float
    change: float = 0.0
    change_percent: float = 0.0
    previous_close: float = 0.0


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class ValidationError:
    rule: str
    field: str
    value: object
    message: str


@dataclass
class PriceValidationResult:
    valid: list[RawPriceRecord] = field(default_factory=list)
    rejected: list[tuple[RawPriceRecord, list[ValidationError]]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ingestion report  (returned by IngestionService.run())
# ---------------------------------------------------------------------------

@dataclass
class IngestionReport:
    source: str
    started_at: datetime
    finished_at: datetime
    status: str                      # "success" | "failure"
    instruments_upserted: int = 0
    snapshots_inserted: int = 0
    snapshots_skipped: int = 0
    prices_accepted: int = 0
    prices_skipped: int = 0
    prices_replaced: int = 0
    prices_rejected: int = 0
    rejection_summary: list[str] = field(default_factory=list)
    error_detail: str | None = None

    def __str__(self) -> str:  # pragma: no cover
        lines = [
            f"Ingestion report — source={self.source}  status={self.status}",
            f"  Duration   : {(self.finished_at - self.started_at).total_seconds():.2f}s",
            f"  Instruments: {self.instruments_upserted} upserted",
            f"  Snapshots  : {self.snapshots_inserted} inserted, {self.snapshots_skipped} skipped",
            f"  Prices     : {self.prices_accepted} accepted, "
            f"{self.prices_skipped} skipped, "
            f"{self.prices_replaced} replaced, "
            f"{self.prices_rejected} rejected",
        ]
        if self.rejection_summary:
            lines.append("  Rejections :")
            for r in self.rejection_summary:
                lines.append(f"    {r}")
        if self.error_detail:
            lines.append(f"  Error      : {self.error_detail}")
        return "\n".join(lines)
