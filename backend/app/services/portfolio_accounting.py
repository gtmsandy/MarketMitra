"""Deterministic, persistence-free portfolio accounting rules.

All quantities and monetary values use Decimal and are rounded half-up to eight
decimal places. Persistence, authorization, and valuation-price retrieval stay
outside this module so the accounting rules can be tested independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re
from typing import Iterable, Literal, Mapping


QUANTUM = Decimal("0.00000001")
ZERO = Decimal("0.00000000")
_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,31}$")


class PortfolioAccountingError(ValueError):
    """Base error for invalid or impossible accounting operations."""


class FinancialValidationError(PortfolioAccountingError):
    """A transaction or valuation violates a financial input contract."""


class DuplicateTransactionError(PortfolioAccountingError):
    """A transaction identifier was submitted more than once."""


class OversellError(PortfolioAccountingError):
    """A sell would make a holding quantity negative."""


def _decimal(value: object, field: str) -> Decimal:
    if isinstance(value, (bool, float)) or not isinstance(value, (Decimal, str, int)):
        raise FinancialValidationError(f"{field} must be a Decimal, integer, or string")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise FinancialValidationError(f"{field} must be a valid decimal") from exc
    if not parsed.is_finite():
        raise FinancialValidationError(f"{field} must be finite")
    return parsed.quantize(QUANTUM, rounding=ROUND_HALF_UP)


def _calculated(field: str, operation) -> Decimal:
    """Evaluate arithmetic above the 28-digit default Decimal context."""
    with localcontext() as context:
        context.prec = 50
        try:
            value = operation()
        except (InvalidOperation, ZeroDivisionError) as exc:
            raise FinancialValidationError(f"{field} cannot be calculated") from exc
    return _decimal(value, field)


def _positive(value: object, field: str) -> Decimal:
    parsed = _decimal(value, field)
    if parsed <= ZERO:
        raise FinancialValidationError(f"{field} must be positive")
    return parsed


def _nonnegative(value: object, field: str) -> Decimal:
    parsed = _decimal(value, field)
    if parsed < ZERO:
        raise FinancialValidationError(f"{field} must be nonnegative")
    return parsed


@dataclass(frozen=True)
class PortfolioTransaction:
    """An immutable ledger entry; corrections should be compensating entries."""

    transaction_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    trade_date: date
    sequence: int
    quantity: Decimal
    unit_price: Decimal
    fees: Decimal = ZERO
    notes: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.transaction_id, str) or not self.transaction_id.strip():
            raise FinancialValidationError("transaction_id must be non-empty")
        if not isinstance(self.symbol, str) or not _SYMBOL.fullmatch(self.symbol):
            raise FinancialValidationError("symbol must be an uppercase instrument symbol")
        if self.side not in {"BUY", "SELL"}:
            raise FinancialValidationError("side must be BUY or SELL")
        if not isinstance(self.trade_date, date):
            raise FinancialValidationError("trade_date must be a date")
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise FinancialValidationError("sequence must be a nonnegative integer")
        object.__setattr__(self, "quantity", _positive(self.quantity, "quantity"))
        object.__setattr__(self, "unit_price", _positive(self.unit_price, "unit_price"))
        object.__setattr__(self, "fees", _nonnegative(self.fees, "fees"))


@dataclass(frozen=True)
class Holding:
    symbol: str
    quantity: Decimal
    carrying_cost: Decimal
    average_cost: Decimal


@dataclass(frozen=True)
class PortfolioLedgerState:
    holdings: Mapping[str, Holding]
    realized_pnl: Decimal
    total_buy_cost: Decimal
    applied_transaction_ids: tuple[str, ...]


@dataclass(frozen=True)
class ValuationObservation:
    symbol: str
    price: Decimal
    observed_on: date
    sector: str | None
    data_freshness: str

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not _SYMBOL.fullmatch(self.symbol):
            raise FinancialValidationError("valuation symbol must be an uppercase instrument symbol")
        object.__setattr__(self, "price", _positive(self.price, "valuation price"))
        if not isinstance(self.observed_on, date):
            raise FinancialValidationError("observed_on must be a date")
        if not isinstance(self.data_freshness, str) or not self.data_freshness.strip():
            raise FinancialValidationError("data_freshness must be non-empty")

    def is_stale(self, as_of: date, stale_after_days: int) -> bool:
        if not isinstance(as_of, date) or as_of < self.observed_on:
            raise FinancialValidationError("valuation date cannot precede the observation")
        if isinstance(stale_after_days, bool) or stale_after_days < 0:
            raise FinancialValidationError("stale_after_days must be nonnegative")
        return (as_of - self.observed_on).days > stale_after_days


@dataclass(frozen=True)
class SectorAllocation:
    sector: str
    market_value: Decimal
    percentage: Decimal


@dataclass(frozen=True)
class PortfolioSummary:
    carrying_cost: Decimal
    market_value: Decimal | None
    realized_pnl: Decimal
    unrealized_pnl: Decimal | None
    total_pnl: Decimal | None
    return_percent: Decimal | None
    valuation_status: Literal["complete", "incomplete"]
    missing_symbols: tuple[str, ...]
    stale_symbols: tuple[str, ...]
    sector_allocation: tuple[SectorAllocation, ...]


def replay_transactions(transactions: Iterable[PortfolioTransaction]) -> PortfolioLedgerState:
    """Replay a ledger in deterministic order, rejecting duplicate IDs and oversells."""

    items = list(transactions)
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, PortfolioTransaction):
            raise FinancialValidationError("transactions must contain PortfolioTransaction values")
        if item.transaction_id in seen:
            raise DuplicateTransactionError(f"duplicate transaction: {item.transaction_id}")
        seen.add(item.transaction_id)

    holdings: dict[str, Holding] = {}
    realized_pnl = ZERO
    total_buy_cost = ZERO
    applied_ids: list[str] = []

    for item in sorted(items, key=lambda value: (value.trade_date, value.sequence, value.transaction_id)):
        current = holdings.get(item.symbol, Holding(item.symbol, ZERO, ZERO, ZERO))
        if item.side == "BUY":
            gross_cost = _calculated("buy cost", lambda: item.quantity * item.unit_price + item.fees)
            quantity = _calculated("holding quantity", lambda: current.quantity + item.quantity)
            carrying_cost = _calculated("carrying cost", lambda: current.carrying_cost + gross_cost)
            holdings[item.symbol] = Holding(
                item.symbol,
                quantity,
                carrying_cost,
                _calculated("average cost", lambda: carrying_cost / quantity),
            )
            total_buy_cost = _calculated("total buy cost", lambda: total_buy_cost + gross_cost)
        else:
            if item.quantity > current.quantity:
                raise OversellError(
                    f"cannot sell {item.quantity} {item.symbol}; available quantity is {current.quantity}"
                )
            cost_basis = _calculated("sell cost basis", lambda: item.quantity * current.average_cost)
            proceeds = _calculated("sell proceeds", lambda: item.quantity * item.unit_price - item.fees)
            realized_pnl = _calculated("realized pnl", lambda: realized_pnl + proceeds - cost_basis)
            quantity = _calculated("holding quantity", lambda: current.quantity - item.quantity)
            if quantity == ZERO:
                holdings[item.symbol] = Holding(item.symbol, ZERO, ZERO, ZERO)
            else:
                holdings[item.symbol] = Holding(
                    item.symbol,
                    quantity,
                    _calculated("carrying cost", lambda: current.carrying_cost - cost_basis),
                    current.average_cost,
                )
        applied_ids.append(item.transaction_id)

    return PortfolioLedgerState(
        holdings=dict(holdings),
        realized_pnl=realized_pnl,
        total_buy_cost=total_buy_cost,
        applied_transaction_ids=tuple(applied_ids),
    )


def portfolio_summary(
    state: PortfolioLedgerState,
    valuations: Mapping[str, ValuationObservation],
    *,
    as_of: date,
    stale_after_days: int = 3,
) -> PortfolioSummary:
    """Summarize a replayed ledger without claiming incomplete valuation is current."""

    active = [holding for holding in state.holdings.values() if holding.quantity > ZERO]
    carrying_cost = _calculated("carrying cost", lambda: sum((holding.carrying_cost for holding in active), ZERO))
    if not active:
        return_percent = (
            ZERO
            if state.total_buy_cost == ZERO
            else _calculated("return percent", lambda: state.realized_pnl * Decimal("100") / state.total_buy_cost)
        )
        return PortfolioSummary(
            carrying_cost=ZERO,
            market_value=ZERO,
            realized_pnl=state.realized_pnl,
            unrealized_pnl=ZERO,
            total_pnl=state.realized_pnl,
            return_percent=return_percent,
            valuation_status="complete",
            missing_symbols=(),
            stale_symbols=(),
            sector_allocation=(),
        )

    missing = sorted(holding.symbol for holding in active if holding.symbol not in valuations)
    stale = sorted(
        holding.symbol
        for holding in active
        if holding.symbol in valuations and valuations[holding.symbol].is_stale(as_of, stale_after_days)
    )
    if missing or stale:
        return PortfolioSummary(
            carrying_cost=carrying_cost,
            market_value=None,
            realized_pnl=state.realized_pnl,
            unrealized_pnl=None,
            total_pnl=None,
            return_percent=None,
            valuation_status="incomplete",
            missing_symbols=tuple(missing),
            stale_symbols=tuple(stale),
            sector_allocation=(),
        )

    values: dict[str, Decimal] = {
        holding.symbol: _calculated("market value", lambda: holding.quantity * valuations[holding.symbol].price)
        for holding in active
    }
    market_value = _calculated("market value", lambda: sum(values.values(), ZERO))
    unrealized_pnl = _calculated("unrealized pnl", lambda: market_value - carrying_cost)
    total_pnl = _calculated("total pnl", lambda: state.realized_pnl + unrealized_pnl)
    return_percent = (
        ZERO
        if state.total_buy_cost == ZERO
        else _calculated("return percent", lambda: total_pnl * Decimal("100") / state.total_buy_cost)
    )
    sector_values: dict[str, Decimal] = {}
    for symbol, value in values.items():
        sector = valuations[symbol].sector or "Unclassified"
        sector_values[sector] = _calculated("sector market value", lambda: sector_values.get(sector, ZERO) + value)
    allocations = tuple(
        SectorAllocation(
            sector=sector,
            market_value=value,
            percentage=_calculated("sector percentage", lambda: value * Decimal("100") / market_value),
        )
        for sector, value in sorted(sector_values.items())
    )
    return PortfolioSummary(
        carrying_cost=carrying_cost,
        market_value=market_value,
        realized_pnl=state.realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        return_percent=return_percent,
        valuation_status="complete",
        missing_symbols=(),
        stale_symbols=(),
        sector_allocation=allocations,
    )
