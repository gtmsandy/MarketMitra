from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.db.models import DailyPrice, Instrument


def _register(client, email: str):
    response = client.post("/api/v1/auth/register", json={"email": email, "display_name": "Demo", "password": "Strong-password-123!"})
    assert response.status_code == 201
    return response.json()["csrf_token"]


def _seed_instrument(factory, symbol="SYNBANKA"):
    with factory() as session:
        session.add(Instrument(symbol=symbol, company_name="Synthetic Bank", sector="Banks", created_at=datetime.now(timezone.utc)))
        session.commit()


def _seed_price(factory, symbol="SYNBANKA", close=105):
    with factory() as session:
        session.add(DailyPrice(symbol=symbol, date=str(date.today()), open=100, high=106, low=99, close=close, volume=100, turnover=10_500, previous_close=100))
        session.commit()


def test_portfolio_owner_scoping_and_archive(identity_client, identity_session_factory):
    csrf = _register(identity_client, "owner@example.test")
    _seed_instrument(identity_session_factory)
    created = identity_client.post("/api/v1/portfolios", headers={"Origin": "http://localhost:5173", "X-CSRF-Token": csrf}, json={"name": "Retirement"})
    assert created.status_code == 201
    portfolio_id = created.json()["id"]
    assert identity_client.get("/api/v1/portfolios").json()[0]["name"] == "Retirement"
    archived = identity_client.delete(f"/api/v1/portfolios/{portfolio_id}", headers={"Origin": "http://localhost:5173", "X-CSRF-Token": csrf})
    assert archived.status_code == 204
    assert identity_client.get(f"/api/v1/portfolios/{portfolio_id}").json()["archived_at"] is not None


def test_portfolio_isolation_rejects_other_user(identity_client, identity_session_factory):
    first_csrf = _register(identity_client, "first@example.test")
    _seed_instrument(identity_session_factory)
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": first_csrf}
    portfolio = identity_client.post("/api/v1/portfolios", headers=headers, json={"name": "Private"}).json()
    identity_client.post("/api/v1/auth/logout", headers=headers)
    second_csrf = _register(identity_client, "second@example.test")
    assert identity_client.get(f"/api/v1/portfolios/{portfolio['id']}").status_code == 404
    assert identity_client.get(f"/api/v1/portfolios/{portfolio['id']}/transactions").status_code == 404
    assert identity_client.post(f"/api/v1/portfolios/{portfolio['id']}/transactions", headers={"Origin": "http://localhost:5173", "X-CSRF-Token": second_csrf}, json={"idempotency_key": str(uuid4()), "symbol": "SYNBANKA", "side": "BUY", "trade_date": str(date.today()), "quantity": "1", "unit_price": "1", "fees": "0"}).status_code == 404


def test_transaction_idempotency_and_summary(identity_client, identity_session_factory):
    csrf = _register(identity_client, "trader@example.test")
    _seed_instrument(identity_session_factory)
    _seed_price(identity_session_factory)
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf}
    portfolio = identity_client.post("/api/v1/portfolios", headers=headers, json={"name": "Trading"}).json()
    key = str(uuid4())
    payload = {"idempotency_key": key, "symbol": "SYNBANKA", "side": "BUY", "trade_date": str(date.today()), "quantity": "2", "unit_price": "100", "fees": "1"}
    first = identity_client.post(f"/api/v1/portfolios/{portfolio['id']}/transactions", headers=headers, json=payload)
    assert first.status_code == 201
    assert first.json()["gross_value"] == "200.00000000"
    replay = identity_client.post(f"/api/v1/portfolios/{portfolio['id']}/transactions", headers=headers, json=payload)
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    conflict = identity_client.post(f"/api/v1/portfolios/{portfolio['id']}/transactions", headers=headers, json={**payload, "quantity": "3"})
    assert conflict.status_code == 409
    summary = identity_client.get(f"/api/v1/portfolios/{portfolio['id']}/summary")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["total_acquisition_cost"] == "201.00000000"
    assert payload["holdings"][0] == {
        "symbol": "SYNBANKA",
        "company_name": "Synthetic Bank",
        "quantity": "2.00000000",
        "average_cost": "100.50000000",
        "invested_cost": "201.00000000",
        "realized_pnl": "0E-8",
        "valuation_price": "105.00000000",
        "valuation_observed_on": str(date.today()),
        "unrealized_pnl": "9.00000000",
    }


def test_future_trade_and_oversell_rejected(identity_client, identity_session_factory):
    csrf = _register(identity_client, "risk@example.test")
    _seed_instrument(identity_session_factory)
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf}
    portfolio = identity_client.post("/api/v1/portfolios", headers=headers, json={"name": "Risk"}).json()
    base = {"idempotency_key": str(uuid4()), "symbol": "SYNBANKA", "side": "SELL", "trade_date": "2099-01-01", "quantity": "1", "unit_price": "100", "fees": "0"}
    assert identity_client.post(f"/api/v1/portfolios/{portfolio['id']}/transactions", headers=headers, json=base).status_code == 400
    base["trade_date"] = str(date.today())
    assert identity_client.post(f"/api/v1/portfolios/{portfolio['id']}/transactions", headers=headers, json=base).status_code == 400
