from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Instrument(Base):
    """A listed stock or security."""

    __tablename__ = "instruments"

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    sector: Mapped[str | None] = mapped_column(String, nullable=True)
    security_type: Mapped[str] = mapped_column(
        String, nullable=False, default="EQUITY", server_default="EQUITY", index=True
    )
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
    turnover: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_transactions: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    is_ohlc_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", index=True)
    validation_reason: Mapped[str | None] = mapped_column(String, nullable=True)

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


class LiveQuote(Base):
    """Real-time or intraday price quote observation."""

    __tablename__ = "live_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(
        String, ForeignKey("instruments.symbol", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)  # Current LTP
    volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    turnover: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="unspecified")
    source_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    instrument: Mapped["Instrument"] = relationship("Instrument")
    __table_args__ = (
        UniqueConstraint("symbol", "timestamp", name="uq_live_quotes_symbol_timestamp"),
        Index("ix_live_quotes_symbol_timestamp", "symbol", "timestamp"),
    )
