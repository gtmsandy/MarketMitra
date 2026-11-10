"""Owner-scoped portfolio persistence around the pure accounting engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import hashlib
import json
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import DailyPrice, Instrument, Portfolio, PortfolioTransaction
from app.services.portfolio_accounting import (
    FinancialValidationError,
    OversellError,
    PortfolioTransaction as AccountingTransaction,
    ValuationObservation,
    portfolio_summary,
    replay_transactions,
)


class PortfolioError(ValueError):
    pass


class NotFoundError(PortfolioError):
    pass


class ConflictError(PortfolioError):
    pass


class ValidationError(PortfolioError):
    pass


def _fingerprint(payload: dict[str, object]) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _owned(session: Session, owner_id: UUID, portfolio_id: UUID, *, include_archived: bool = False) -> Portfolio:
    query = select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.owner_id == owner_id)
    if not include_archived:
        query = query.where(Portfolio.archived_at.is_(None))
    portfolio = session.scalar(query)
    if portfolio is None:
        raise NotFoundError("Portfolio not found")
    return portfolio


def create_portfolio(session: Session, owner_id: UUID, name: str) -> Portfolio:
    portfolio = Portfolio(owner_id=owner_id, name=name, base_currency="NPR")
    session.add(portfolio)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Portfolio name is already in use") from exc
    return portfolio


def list_portfolios(session: Session, owner_id: UUID) -> list[Portfolio]:
    return list(session.scalars(select(Portfolio).where(Portfolio.owner_id == owner_id).order_by(Portfolio.created_at, Portfolio.name)).all())


def rename_portfolio(session: Session, owner_id: UUID, portfolio_id: UUID, name: str) -> Portfolio:
    portfolio = _owned(session, owner_id, portfolio_id)
    portfolio.name = name
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("Portfolio name is already in use") from exc
    return portfolio


def archive_portfolio(session: Session, owner_id: UUID, portfolio_id: UUID) -> Portfolio:
    portfolio = _owned(session, owner_id, portfolio_id)
    from datetime import datetime, timezone
    portfolio.archived_at = datetime.now(timezone.utc)
    return portfolio


def _accounting_rows(session: Session, portfolio_id: UUID) -> list[PortfolioTransaction]:
    return list(session.scalars(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id == portfolio_id).order_by(PortfolioTransaction.trade_date, PortfolioTransaction.trade_sequence, PortfolioTransaction.id)).all())


def _accounting(row: PortfolioTransaction) -> AccountingTransaction:
    return AccountingTransaction(
        transaction_id=str(row.id), symbol=row.symbol, side=row.side, trade_date=row.trade_date,
        sequence=row.trade_sequence, quantity=Decimal(row.quantity), unit_price=Decimal(row.unit_price),
        fees=Decimal(row.fees), notes=row.notes,
    )


def create_transaction(session: Session, owner_id: UUID, portfolio_id: UUID, payload: dict[str, object]) -> tuple[PortfolioTransaction, bool]:
    portfolio = _owned(session, owner_id, portfolio_id)
    portfolio = session.scalar(select(Portfolio).where(Portfolio.id == portfolio.id).with_for_update()) or portfolio
    trade_date = payload["trade_date"]
    if not isinstance(trade_date, date) or trade_date > date.today():
        raise ValidationError("Trade date cannot be in the future")
    symbol = str(payload["symbol"])
    if session.scalar(select(Instrument).where(Instrument.symbol == symbol)) is None:
        raise NotFoundError("Instrument not found")
    key = payload["idempotency_key"]
    fingerprint = _fingerprint(payload)
    existing = session.scalar(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id == portfolio.id, PortfolioTransaction.idempotency_key == key))
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise ConflictError("Idempotency key was already used for another request")
        return existing, False
    sequence = session.scalar(select(func.coalesce(func.max(PortfolioTransaction.trade_sequence), -1) + 1).where(PortfolioTransaction.portfolio_id == portfolio.id, PortfolioTransaction.trade_date == trade_date))
    row = PortfolioTransaction(
        portfolio_id=portfolio.id, symbol=symbol, side=str(payload["side"]), trade_date=trade_date,
        trade_sequence=int(sequence or 0), quantity=payload["quantity"], unit_price=payload["unit_price"],
        fees=payload["fees"], idempotency_key=key, request_fingerprint=fingerprint, notes=payload.get("notes"),
    )
    try:
        replay_transactions([_accounting(existing_row) for existing_row in _accounting_rows(session, portfolio.id)] + [_accounting(row)])
    except OversellError as exc:
        raise ValidationError(str(exc)) from exc
    except FinancialValidationError as exc:
        raise ValidationError(str(exc)) from exc
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(select(PortfolioTransaction).where(PortfolioTransaction.portfolio_id == portfolio.id, PortfolioTransaction.idempotency_key == key))
        if existing is not None and existing.request_fingerprint == fingerprint:
            return existing, False
        raise ConflictError("Transaction conflicts with an existing portfolio entry")
    return row, True


def holdings_and_summary(session: Session, owner_id: UUID, portfolio_id: UUID, as_of: date):
    portfolio = _owned(session, owner_id, portfolio_id)
    rows = _accounting_rows(session, portfolio.id)
    state = replay_transactions([_accounting(row) for row in rows])
    active = [holding for holding in state.holdings.values() if holding.quantity > 0]
    valuations: dict[str, ValuationObservation] = {}
    for holding in active:
        price = session.execute(
            select(DailyPrice, Instrument).join(Instrument, Instrument.symbol == DailyPrice.symbol)
            .where(DailyPrice.symbol == holding.symbol, DailyPrice.date <= as_of.isoformat())
            .order_by(DailyPrice.date.desc()).limit(1)
        ).first()
        if price:
            daily, instrument = price
            valuations[holding.symbol] = ValuationObservation(
                symbol=holding.symbol, price=Decimal(str(daily.close)), observed_on=date.fromisoformat(daily.date),
                sector=instrument.sector, data_freshness="SYNTHETIC_HISTORICAL",
            )
    summary = portfolio_summary(state, valuations, as_of=as_of)
    return state, summary, valuations


def transaction_to_dict(row: PortfolioTransaction) -> dict[str, object]:
    return {
        "id": row.id, "portfolio_id": row.portfolio_id, "symbol": row.symbol, "side": row.side,
        "trade_date": row.trade_date, "trade_sequence": row.trade_sequence, "quantity": row.quantity,
        "unit_price": row.unit_price, "fees": row.fees, "idempotency_key": row.idempotency_key,
        "notes": row.notes, "created_at": row.created_at,
    }
