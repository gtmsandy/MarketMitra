from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from app.db.models import Instrument, User
from app.identity.service import provision_admin


def _register(client: TestClient, email: str) -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "Watchlist Investor",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201
    return response.cookies["marketmitra_session"], response.json()["csrf_token"]


def _seed_instrument(factory: sessionmaker[Session], symbol: str = "NABIL") -> None:
    with factory() as session:
        session.add(
            Instrument(
                symbol=symbol,
                company_name="Nabil Bank",
                sector="Banking",
                security_type="EQUITY",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def test_watchlist_crud_requires_csrf_and_returns_instrument_data(
    identity_client: TestClient,
    identity_session_factory: sessionmaker[Session],
) -> None:
    _seed_instrument(identity_session_factory)
    _, csrf = _register(identity_client, "watchlist@example.com")
    headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": csrf}

    missing_csrf = identity_client.post(
        "/api/v1/watchlists", json={"name": "Research"}, headers={"Origin": headers["Origin"]}
    )
    assert missing_csrf.status_code == 403

    created = identity_client.post(
        "/api/v1/watchlists", json={"name": "  Research  "}, headers=headers
    )
    assert created.status_code == 201
    watchlist = created.json()
    assert watchlist["name"] == "research"
    watchlist_id = watchlist["id"]

    invalid_instrument = identity_client.post(
        f"/api/v1/watchlists/{watchlist_id}/items",
        json={"symbol": "UNKNOWN"},
        headers=headers,
    )
    assert invalid_instrument.status_code == 404

    added = identity_client.post(
        f"/api/v1/watchlists/{watchlist_id}/items",
        json={"symbol": " nabil "},
        headers=headers,
    )
    assert added.status_code == 200
    assert added.json()["items"][0]["symbol"] == "NABIL"
    assert added.json()["items"][0]["company_name"] == "Nabil Bank"

    duplicate = identity_client.post(
        f"/api/v1/watchlists/{watchlist_id}/items", json={"symbol": "NABIL"}, headers=headers
    )
    assert duplicate.status_code == 409

    renamed = identity_client.patch(
        f"/api/v1/watchlists/{watchlist_id}", json={"name": "Long term"}, headers=headers
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "long term"

    removed = identity_client.delete(
        f"/api/v1/watchlists/{watchlist_id}/items/NABIL", headers=headers
    )
    assert removed.status_code == 200
    assert removed.json()["items"] == []

    deleted = identity_client.delete(f"/api/v1/watchlists/{watchlist_id}", headers=headers)
    assert deleted.status_code == 204
    assert identity_client.get(f"/api/v1/watchlists/{watchlist_id}").status_code == 404


def test_watchlists_are_owner_scoped_and_admin_is_not_privileged_over_user_data(
    identity_client: TestClient,
    identity_session_factory: sessionmaker[Session],
) -> None:
    _, first_csrf = _register(identity_client, "first@example.com")
    first_headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": first_csrf}
    created = identity_client.post(
        "/api/v1/watchlists", json={"name": "Private"}, headers=first_headers
    )
    assert created.status_code == 201
    watchlist_id = created.json()["id"]

    identity_client.post(
        "/api/v1/auth/logout", headers=first_headers
    )
    second_login = identity_client.post(
        "/api/v1/auth/login",
        json={"email": "second@example.com", "password": "correct horse battery staple"},
    )
    assert second_login.status_code == 401
    _, second_csrf = _register(identity_client, "second@example.com")
    second_headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": second_csrf}

    assert identity_client.get(f"/api/v1/watchlists/{watchlist_id}").status_code == 404
    assert identity_client.patch(
        f"/api/v1/watchlists/{watchlist_id}", json={"name": "stolen"}, headers=second_headers
    ).status_code == 404
    assert identity_client.delete(
        f"/api/v1/watchlists/{watchlist_id}", headers=second_headers
    ).status_code == 404

    with identity_session_factory() as session:
        assert session.scalar(select(User).where(User.email == "first@example.com")) is not None


def test_admin_only_sees_admin_owned_watchlists(
    identity_client: TestClient,
    identity_session_factory: sessionmaker[Session],
) -> None:
    _, first_csrf = _register(identity_client, "private-owner@example.com")
    first_headers = {"Origin": "http://localhost:5173", "X-CSRF-Token": first_csrf}
    created = identity_client.post(
        "/api/v1/watchlists", json={"name": "Owner only"}, headers=first_headers
    )
    assert created.status_code == 201
    identity_client.post("/api/v1/auth/logout", headers=first_headers)

    with identity_session_factory.begin() as session:
        provision_admin(
            session,
            email="watchlist-admin@example.com",
            display_name="Watchlist Admin",
            password="correct horse battery staple",
        )

    login = identity_client.post(
        "/api/v1/auth/login",
        json={"email": "watchlist-admin@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    assert identity_client.get("/api/v1/watchlists").json() == []
