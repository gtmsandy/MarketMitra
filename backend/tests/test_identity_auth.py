from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_identity_session
from app.db.base import Base
from app.db.models import SecurityAuditEvent, User, UserSession
from app.identity.security import verifier_matches, verify_password
from app.main import app


@pytest.fixture
def identity_session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def identity_client(
    identity_session_factory: sessionmaker[Session],
) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        with identity_session_factory() as session:
            yield session

    app.dependency_overrides[get_identity_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_identity_session, None)


def test_register_creates_user_hashed_credentials_and_audit_event(
    identity_client: TestClient,
    identity_session_factory: sessionmaker[Session],
) -> None:
    response = identity_client.post(
        "/api/v1/auth/register",
        json={
            "email": "  Investor@Example.COM ",
            "display_name": "  Anika Investor  ",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "investor@example.com"
    assert body["user"]["display_name"] == "Anika Investor"
    assert body["user"]["role"] == "USER"
    assert body["csrf_token"]
    assert body["expires_at"] > datetime.now(timezone.utc).isoformat()

    cookie = response.cookies.get("marketmitra_session")
    assert cookie
    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/api/v1" in set_cookie

    with identity_session_factory() as session:
        user = session.scalar(select(User))
        stored_session = session.scalar(select(UserSession))
        event = session.scalar(select(SecurityAuditEvent))

        assert user is not None
        assert user.password_hash != "correct horse battery staple"
        assert verify_password(user.password_hash, "correct horse battery staple")
        assert stored_session is not None
        assert verifier_matches(stored_session.token_verifier, cookie)
        assert verifier_matches(stored_session.csrf_verifier, body["csrf_token"])
        assert event is not None
        assert event.event_type == "IDENTITY_REGISTERED"
        assert event.outcome == "SUCCESS"
        assert event.event_metadata == {}


@pytest.mark.parametrize(
    "payload",
    [
        {
            "email": "not-an-email",
            "display_name": "Investor",
            "password": "correct horse battery staple",
        },
        {
            "email": "investor@example.com",
            "display_name": " ",
            "password": "correct horse battery staple",
        },
        {
            "email": "investor@example.com",
            "display_name": "Investor",
            "password": "short",
        },
    ],
)
def test_register_rejects_invalid_boundary_input(
    identity_client: TestClient, payload: dict[str, str]
) -> None:
    response = identity_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


def test_register_duplicate_email_uses_generic_conflict(
    identity_client: TestClient,
) -> None:
    payload = {
        "email": "investor@example.com",
        "display_name": "Investor",
        "password": "correct horse battery staple",
    }
    assert identity_client.post("/api/v1/auth/register", json=payload).status_code == 201

    response = identity_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "REGISTRATION_UNAVAILABLE",
            "message": "Registration could not be completed",
        }
    }


def test_login_returns_same_generic_error_for_unknown_email_and_bad_password(
    identity_client: TestClient,
) -> None:
    registration = {
        "email": "investor@example.com",
        "display_name": "Investor",
        "password": "correct horse battery staple",
    }
    assert identity_client.post("/api/v1/auth/register", json=registration).status_code == 201

    unknown = identity_client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "incorrect password value"},
    )
    incorrect = identity_client.post(
        "/api/v1/auth/login",
        json={"email": "investor@example.com", "password": "incorrect password value"},
    )

    expected = {
        "error": {
            "code": "AUTHENTICATION_FAILED",
            "message": "Email or password is incorrect",
        }
    }
    assert unknown.status_code == incorrect.status_code == 401
    assert unknown.json() == incorrect.json() == expected


def test_login_creates_a_new_hashed_session(
    identity_client: TestClient,
    identity_session_factory: sessionmaker[Session],
) -> None:
    registration = {
        "email": "investor@example.com",
        "display_name": "Investor",
        "password": "correct horse battery staple",
    }
    assert identity_client.post("/api/v1/auth/register", json=registration).status_code == 201

    response = identity_client.post(
        "/api/v1/auth/login",
        json={
            "email": " INVESTOR@example.com ",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "investor@example.com"
    assert response.cookies.get("marketmitra_session")
    with identity_session_factory() as session:
        assert len(session.scalars(select(UserSession)).all()) == 2
        events = session.scalars(
            select(SecurityAuditEvent).order_by(SecurityAuditEvent.created_at)
        ).all()
        assert [event.event_type for event in events] == [
            "IDENTITY_REGISTERED",
            "IDENTITY_LOGIN",
        ]


def test_auth_cors_preflight_allows_only_configured_credentialed_origin(
    identity_client: TestClient,
) -> None:
    response = identity_client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-csrf-token",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "x-csrf-token" in response.headers["access-control-allow-headers"].lower()
