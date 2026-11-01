from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


class User(Base):
    """A registered MarketMitra identity."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default="USER", server_default="USER"
    )
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("email = lower(trim(email))", name="ck_users_email_normalized"),
        CheckConstraint("role in ('USER', 'ADMIN')", name="ck_users_role"),
        CheckConstraint("state in ('ACTIVE', 'DISABLED')", name="ck_users_state"),
        Index("ix_users_role_state", "role", "state"),
    )


class UserSession(Base):
    """A revocable server-side session with hashed browser credentials."""

    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_verifier: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    csrf_verifier: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rotation_predecessor_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped[User] = relationship("User", back_populates="sessions")

    __table_args__ = (
        UniqueConstraint("token_verifier", name="uq_sessions_token_verifier"),
        UniqueConstraint(
            "rotation_predecessor_id", name="uq_sessions_rotation_predecessor"
        ),
        CheckConstraint(
            "idle_expires_at <= absolute_expires_at",
            name="ck_sessions_expiration_order",
        ),
        CheckConstraint(
            "last_activity_at >= created_at and last_activity_at <= absolute_expires_at",
            name="ck_sessions_activity_window",
        ),
        CheckConstraint(
            "(revoked_at is null and revocation_reason is null) or "
            "(revoked_at is not null and revocation_reason is not null)",
            name="ck_sessions_revocation_pair",
        ),
        Index(
            "ix_sessions_user_active",
            "user_id",
            "absolute_expires_at",
            postgresql_where=text("revoked_at is null"),
        ),
        Index("ix_sessions_idle_expires_at", "idle_expires_at"),
    )


class SecurityAuditEvent(Base):
    """Append-only authentication and authorization security evidence."""

    __tablename__ = "security_audit_events"

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True, autoincrement=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    target_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, default=uuid4)
    event_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    __table_args__ = (
        CheckConstraint(
            "outcome in ('SUCCESS', 'FAILURE', 'DENIED')",
            name="ck_security_audit_events_outcome",
        ),
        Index("ix_security_audit_events_created_at", "created_at"),
        Index("ix_security_audit_events_actor", "actor_user_id", "created_at"),
        Index("ix_security_audit_events_target", "target_user_id", "created_at"),
        Index("ix_security_audit_events_request_id", "request_id"),
    )
