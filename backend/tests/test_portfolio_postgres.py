"""Real PostgreSQL concurrency checks for portfolio ledger writes."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import get_database_url
from app.db.base import make_session_factory
from app.db.models import Portfolio, PortfolioTransaction, User
from app.services.portfolio_service import (
    ConflictError,
    PortfolioError,
    ValidationError,
    create_transaction,
    holdings_and_summary,
)
from tests.postgres_ci import require_disposable_ci_database


@dataclass(frozen=True)
class PortfolioContext:
    owner_id: UUID
    portfolio_id: UUID


@pytest.fixture(scope="module", autouse=True)
def disposable_postgres_only() -> None:
    require_disposable_ci_database()


@pytest.fixture
def portfolio_context() -> PortfolioContext:
    factory = make_session_factory(get_database_url())
    context = PortfolioContext(owner_id=uuid4(), portfolio_id=uuid4())
    with factory.begin() as session:
        session.add(
            User(
                id=context.owner_id,
                email=f"portfolio-concurrency-{context.owner_id}@example.test",
                display_name="Portfolio concurrency",
                password_hash="test-only-not-a-login-secret",
            )
        )
        session.add(Portfolio(id=context.portfolio_id, owner_id=context.owner_id, name=f"Concurrency {context.portfolio_id}"))
    try:
        yield context
    finally:
        with factory.begin() as session:
            session.execute(delete(PortfolioTransaction).where(PortfolioTransaction.portfolio_id == context.portfolio_id))
            session.execute(delete(Portfolio).where(Portfolio.id == context.portfolio_id))
            session.execute(delete(User).where(User.id == context.owner_id))


def _payload(*, side: str, quantity: str, price: str, key: UUID | None = None) -> dict[str, object]:
    return {
        "idempotency_key": key or uuid4(),
        "symbol": "SYNBANKA",
        "side": side,
        "trade_date": date.today(),
        "quantity": quantity,
        "unit_price": price,
        "fees": "0",
        "notes": None,
    }


def _submit_concurrently(context: PortfolioContext, payloads: list[dict[str, object]]) -> list[tuple[str, object]]:
    factory = make_session_factory(get_database_url())
    barrier = Barrier(len(payloads))

    def submit(payload: dict[str, object]) -> tuple[str, object]:
        session: Session = factory()
        try:
            session.execute(text("SET LOCAL lock_timeout = '3s'"))
            barrier.wait(timeout=5)
            transaction, created = create_transaction(session, context.owner_id, context.portfolio_id, payload)
            session.commit()
            return "success", (created, transaction.id, transaction.trade_sequence)
        except PortfolioError as exc:
            session.rollback()
            return "business_error", type(exc).__name__
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=len(payloads)) as executor:
        return [future.result(timeout=10) for future in [executor.submit(submit, payload) for payload in payloads]]


def _transactions(context: PortfolioContext) -> list[PortfolioTransaction]:
    factory = make_session_factory(get_database_url())
    with factory() as session:
        return list(
            session.scalars(
                select(PortfolioTransaction)
                .where(PortfolioTransaction.portfolio_id == context.portfolio_id)
                .order_by(PortfolioTransaction.trade_date, PortfolioTransaction.trade_sequence)
            )
        )


def test_concurrent_oversells_commit_at_most_one_sell(portfolio_context: PortfolioContext) -> None:
    factory = make_session_factory(get_database_url())
    with factory.begin() as session:
        create_transaction(session, portfolio_context.owner_id, portfolio_context.portfolio_id, _payload(side="BUY", quantity="10", price="100"))

    results = _submit_concurrently(
        portfolio_context,
        [_payload(side="SELL", quantity="7", price="110"), _payload(side="SELL", quantity="7", price="110")],
    )

    assert [result[0] for result in results].count("success") == 1
    assert ("business_error", "ValidationError") in results
    with factory() as session:
        state, _, _ = holdings_and_summary(session, portfolio_context.owner_id, portfolio_context.portfolio_id, date.today())
        assert state.holdings["SYNBANKA"].quantity == 3
    assert [transaction.side for transaction in _transactions(portfolio_context)] == ["BUY", "SELL"]


def test_concurrent_identical_idempotency_key_creates_one_logical_transaction(portfolio_context: PortfolioContext) -> None:
    key = uuid4()
    payload = _payload(side="BUY", quantity="2", price="100", key=key)
    results = _submit_concurrently(portfolio_context, [payload, payload.copy()])

    assert {result[0] for result in results} == {"success"}
    assert sorted(result[1][0] for result in results) == [False, True]
    transactions = _transactions(portfolio_context)
    assert len(transactions) == 1
    assert transactions[0].idempotency_key == key


def test_conflicting_idempotency_payload_is_rejected_without_extra_ledger_entry(portfolio_context: PortfolioContext) -> None:
    key = uuid4()
    results = _submit_concurrently(
        portfolio_context,
        [_payload(side="BUY", quantity="2", price="100", key=key), _payload(side="BUY", quantity="2", price="101", key=key)],
    )

    assert [result[0] for result in results].count("success") == 1
    assert ("business_error", "ConflictError") in results
    assert len(_transactions(portfolio_context)) == 1


def test_concurrent_buys_receive_unique_deterministic_sequences(portfolio_context: PortfolioContext) -> None:
    results = _submit_concurrently(
        portfolio_context,
        [_payload(side="BUY", quantity="1", price="100"), _payload(side="BUY", quantity="2", price="120")],
    )

    assert {result[0] for result in results} == {"success"}
    transactions = _transactions(portfolio_context)
    assert [transaction.trade_sequence for transaction in transactions] == [0, 1]
    assert sum(transaction.quantity for transaction in transactions) == 3
