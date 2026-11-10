from datetime import date
from decimal import Decimal

import pytest

from app.services.portfolio_accounting import (
    DuplicateTransactionError,
    FinancialValidationError,
    OversellError,
    PortfolioTransaction,
    ValuationObservation,
    portfolio_summary,
    replay_transactions,
)


def money(value: str) -> Decimal:
    return Decimal(value)


def transaction(
    transaction_id: str,
    side: str,
    quantity: str,
    price: str,
    *,
    trade_date: date = date(2026, 1, 2),
    sequence: int = 1,
    fees: str = "0",
    symbol: str = "SYNBANKA",
) -> PortfolioTransaction:
    return PortfolioTransaction(
        transaction_id=transaction_id,
        symbol=symbol,
        side=side,
        trade_date=trade_date,
        sequence=sequence,
        quantity=money(quantity),
        unit_price=money(price),
        fees=money(fees),
    )


def test_multiple_buys_use_weighted_average_and_capitalize_buy_fees() -> None:
    state = replay_transactions(
        [
            transaction("buy-1", "BUY", "2", "100", fees="1"),
            transaction("buy-2", "BUY", "3", "120", fees="2", sequence=2),
        ]
    )

    holding = state.holdings["SYNBANKA"]
    assert holding.quantity == money("5.00000000")
    assert holding.carrying_cost == money("563.00000000")
    assert holding.average_cost == money("112.60000000")
    assert state.total_buy_cost == money("563.00000000")


def test_partial_sell_reduces_cost_basis_and_records_realized_profit_after_sell_fee() -> None:
    state = replay_transactions(
        [
            transaction("buy", "BUY", "5", "100"),
            transaction("sell", "SELL", "2", "130", fees="3", sequence=2),
        ]
    )

    holding = state.holdings["SYNBANKA"]
    assert holding.quantity == money("3.00000000")
    assert holding.carrying_cost == money("300.00000000")
    assert holding.average_cost == money("100.00000000")
    assert state.realized_pnl == money("57.00000000")


def test_complete_sell_then_buy_again_starts_a_new_position() -> None:
    state = replay_transactions(
        [
            transaction("buy-1", "BUY", "2", "100"),
            transaction("sell-1", "SELL", "2", "110", sequence=2),
            transaction("buy-2", "BUY", "1", "90", sequence=3),
        ]
    )

    holding = state.holdings["SYNBANKA"]
    assert holding.quantity == money("1.00000000")
    assert holding.carrying_cost == money("90.00000000")
    assert state.realized_pnl == money("20.00000000")


def test_transactions_replay_in_trade_date_and_sequence_order() -> None:
    state = replay_transactions(
        [
            transaction("sell", "SELL", "1", "110", trade_date=date(2026, 1, 3), sequence=1),
            transaction("buy", "BUY", "1", "100", trade_date=date(2026, 1, 2), sequence=1),
        ]
    )

    assert state.realized_pnl == money("10.00000000")
    assert state.applied_transaction_ids == ("buy", "sell")


def test_same_day_sequence_is_deterministic_and_tied_sequence_uses_id() -> None:
    transactions = [
        transaction("b", "BUY", "1", "100"),
        transaction("a", "BUY", "1", "90"),
    ]
    first = replay_transactions(transactions)
    second = replay_transactions(list(reversed(transactions)))

    assert first.applied_transaction_ids == second.applied_transaction_ids == ("a", "b")
    assert first.holdings["SYNBANKA"] == second.holdings["SYNBANKA"]


def test_oversell_is_rejected() -> None:
    with pytest.raises(OversellError):
        replay_transactions(
            [
                transaction("buy", "BUY", "1", "100"),
                transaction("sell", "SELL", "1.00000001", "110", sequence=2),
            ]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("quantity", "0"), ("quantity", "-1"), ("fees", "-0.01"), ("unit_price", "0")],
)
def test_invalid_financial_values_are_rejected(field: str, value: str) -> None:
    kwargs = {field: money(value)}
    with pytest.raises(FinancialValidationError):
        PortfolioTransaction(
            transaction_id="invalid",
            symbol="SYNBANKA",
            side="BUY",
            trade_date=date(2026, 1, 2),
            sequence=1,
            quantity=kwargs.get("quantity", money("1")),
            unit_price=kwargs.get("unit_price", money("100")),
            fees=kwargs.get("fees", money("0")),
        )


def test_float_inputs_are_rejected_to_prevent_binary_money() -> None:
    with pytest.raises(FinancialValidationError):
        PortfolioTransaction(
            transaction_id="float",
            symbol="SYNBANKA",
            side="BUY",
            trade_date=date(2026, 1, 2),
            sequence=1,
            quantity=1.5,
            unit_price=100,
            fees=0,
        )


def test_fractional_quantities_and_money_round_half_up_to_eight_places() -> None:
    state = replay_transactions(
        [transaction("fractional", "BUY", "0.123456789", "10.123456789")]
    )

    holding = state.holdings["SYNBANKA"]
    assert holding.quantity == money("0.12345679")
    assert holding.carrying_cost == money("1.24980948")
    assert holding.average_cost == money("10.12345680")


def test_duplicate_transaction_ids_are_rejected() -> None:
    item = transaction("duplicate", "BUY", "1", "100")
    with pytest.raises(DuplicateTransactionError):
        replay_transactions([item, item])


def test_summary_requires_complete_fresh_valuation_for_current_pnl() -> None:
    state = replay_transactions([transaction("buy", "BUY", "2", "100")])
    summary = portfolio_summary(
        state,
        valuations={
            "SYNBANKA": ValuationObservation(
                symbol="SYNBANKA",
                price=money("120"),
                observed_on=date(2026, 1, 2),
                sector="Synthetic Banking",
                data_freshness="HISTORICAL",
            )
        },
        as_of=date(2026, 1, 3),
    )

    assert summary.valuation_status == "complete"
    assert summary.market_value == money("240.00000000")
    assert summary.unrealized_pnl == money("40.00000000")
    assert summary.total_pnl == money("40.00000000")
    assert summary.return_percent == money("20.00000000")
    assert summary.sector_allocation[0].percentage == money("100.00000000")


def test_missing_or_stale_valuation_never_claims_a_current_portfolio_value() -> None:
    state = replay_transactions([transaction("buy", "BUY", "2", "100")])
    stale = portfolio_summary(
        state,
        valuations={
            "SYNBANKA": ValuationObservation(
                symbol="SYNBANKA",
                price=money("120"),
                observed_on=date(2025, 12, 20),
                sector="Synthetic Banking",
                data_freshness="HISTORICAL",
            )
        },
        as_of=date(2026, 1, 3),
        stale_after_days=3,
    )
    missing = portfolio_summary(state, valuations={}, as_of=date(2026, 1, 3))

    for summary in (stale, missing):
        assert summary.valuation_status == "incomplete"
        assert summary.market_value is None
        assert summary.unrealized_pnl is None
        assert summary.total_pnl is None
        assert summary.return_percent is None


def test_realized_pnl_and_return_remain_available_after_position_is_closed() -> None:
    state = replay_transactions(
        [
            transaction("buy", "BUY", "2", "100"),
            transaction("sell", "SELL", "2", "120", sequence=2),
        ]
    )
    summary = portfolio_summary(state, valuations={}, as_of=date(2026, 1, 3))

    assert summary.carrying_cost == money("0.00000000")
    assert summary.realized_pnl == money("40.00000000")
    assert summary.total_pnl == money("40.00000000")
    assert summary.return_percent == money("20.00000000")


def test_empty_portfolio_has_zero_complete_summary() -> None:
    summary = portfolio_summary(replay_transactions([]), valuations={}, as_of=date(2026, 1, 3))

    assert summary.valuation_status == "complete"
    assert summary.market_value == money("0.00000000")
    assert summary.total_pnl == money("0.00000000")
    assert summary.return_percent == money("0.00000000")
