from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Instrument(Base):
    """A listed stock or security."""

    __tablename__ = "instruments"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    sector: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    daily_prices: Mapped[list["DailyPrice"]] = relationship(
        "DailyPrice", back_populates="instrument", cascade="all, delete-orphan"
    )


class MarketSnapshot(Base):
    """A point-in-time capture of market-wide metrics."""

    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nepse_index: Mapped[float] = mapped_column(Float, nullable=False)
    index_change: Mapped[float] = mapped_column(Float, nullable=False)
    index_change_percent: Mapped[float] = mapped_column(Float, nullable=False)
    turnover: Mapped[float] = mapped_column(Float, nullable=False)
    total_volume: Mapped[int] = mapped_column(Integer, nullable=False)
    total_transactions: Mapped[int] = mapped_column(Integer, nullable=False)
    market_status: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class DailyPrice(Base):
    """OHLCV price bar for one instrument on one trading day."""

    __tablename__ = "daily_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(
        String, ForeignKey("instruments.symbol", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[str] = mapped_column(String, nullable=False)  # ISO-8601 YYYY-MM-DD
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    turnover: Mapped[float] = mapped_column(Float, nullable=False)

    # Derived values stored for efficient ranking queries.
    change: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    change_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    previous_close: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    instrument: Mapped["Instrument"] = relationship(
        "Instrument", back_populates="daily_prices"
    )

    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_daily_price_symbol_date"),)


class IngestionRun(Base):
    """Audit record for a single ingestion pipeline execution."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # "success" | "failure"
    instruments_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshots_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshots_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prices_accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prices_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prices_replaced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prices_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
