from collections.abc import Generator
from datetime import datetime, timedelta, timezone

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
from app.security import auth_rate_limiter


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

    auth_rate_limiter.clear()
    app.dependency_overrides[get_identity_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_identity_session, None)
        auth_rate_limiter.clear()


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


def test_session_bootstrap_rotates_csrf_and_rejects_the_previous_token(
    identity_client: TestClient,
    identity_session_factory: sessionmaker[Session],
) -> None:
    registration = identity_client.post(
        "/api/v1/auth/register",
        json={
            "email": "investor@example.com",
            "display_name": "Investor",
            "password": "correct horse battery staple",
        },
    )
    original_csrf = registration.json()["csrf_token"]
    original_cookie = registration.cookies.get("marketmitra_session")
    assert original_cookie

    bootstrap = identity_client.get("/api/v1/auth/session")

    assert bootstrap.status_code == 200
    rotated_csrf = bootstrap.json()["csrf_token"]
    rotated_cookie = bootstrap.cookies.get("marketmitra_session")
    assert rotated_cookie
    assert rotated_cookie != original_cookie
    assert rotated_csrf != original_csrf
    with identity_session_factory() as session:
        sessions = session.scalars(
            select(UserSession).order_by(UserSession.created_at)
        ).all()
        assert len(sessions) == 2
        assert sessions[0].revocation_reason == "ROTATED"
        assert sessions[1].rotation_predecessor_id == sessions[0].id

    identity_client.cookies.set(
        "marketmitra_session", original_cookie, path="/api/v1"
    )
    assert identity_client.get("/api/v1/auth/session").status_code == 401
    identity_client.cookies.set(
        "marketmitra_session", rotated_cookie, path="/api/v1"
    )
    rejected = identity_client.post(
        "/api/v1/auth/logout",
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": original_csrf,
        },
    )
    assert rejected.status_code == 403
    accepted = identity_client.post(
        "/api/v1/auth/logout",
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": rotated_csrf,
        },
    )
    assert accepted.status_code == 204
    assert "Max-Age=0" in accepted.headers["set-cookie"]


def test_login_rate_limit_is_bounded_and_generic(
    identity_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTH_RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "900")
    payload = {"email": "unknown@example.com", "password": "incorrect password value"}

    first = identity_client.post("/api/v1/auth/login", json=payload)
    second = identity_client.post("/api/v1/auth/login", json=payload)
    limited = identity_client.post("/api/v1/auth/login", json=payload)

    assert first.status_code == second.status_code == 401
    assert limited.status_code == 429
    assert limited.json() == {
        "error": {
            "code": "RATE_LIMITED",
            "message": "Too many authentication attempts",
        }
    }
    assert int(limited.headers["retry-after"]) > 0


@pytest.mark.parametrize(
    "headers",
    [
        {"X-CSRF-Token": "invalid"},
        {"Origin": "https://attacker.example", "X-CSRF-Token": "invalid"},
        {"Origin": "http://localhost:5173", "X-CSRF-Token": "invalid"},
    ],
)
def test_logout_uses_one_generic_csrf_failure(
    identity_client: TestClient, headers: dict[str, str]
) -> None:
    identity_client.post(
        "/api/v1/auth/register",
        json={
            "email": "investor@example.com",
            "display_name": "Investor",
            "password": "correct horse battery staple",
        },
    )

    response = identity_client.post("/api/v1/auth/logout", headers=headers)

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "CSRF_VALIDATION_FAILED",
            "message": "Request could not be verified",
        }
    }


@pytest.mark.parametrize(
    "idle_delta, absolute_delta, reason",
    [
        (timedelta(seconds=-1), timedelta(hours=1), "IDLE_EXPIRED"),
        (timedelta(seconds=-2), timedelta(seconds=-1), "ABSOLUTE_EXPIRED"),
    ],
)
def test_expired_session_is_revoked_and_cookie_is_cleared(
    identity_client: TestClient,
    identity_session_factory: sessionmaker[Session],
    idle_delta: timedelta,
    absolute_delta: timedelta,
    reason: str,
) -> None:
    identity_client.post(
        "/api/v1/auth/register",
        json={
            "email": "investor@example.com",
            "display_name": "Investor",
            "password": "correct horse battery staple",
        },
    )
    now = datetime.now(timezone.utc)
    with identity_session_factory() as session:
        stored = session.scalar(select(UserSession))
        assert stored is not None
        stored.created_at = now - timedelta(hours=2)
        stored.last_activity_at = now - timedelta(hours=1)
        stored.idle_expires_at = now + idle_delta
        stored.absolute_expires_at = now + absolute_delta
        session.commit()

    response = identity_client.get("/api/v1/auth/session")

    assert response.status_code == 401
    assert "Max-Age=0" in response.headers["set-cookie"]
    with identity_session_factory() as session:
        stored = session.scalar(select(UserSession))
        assert stored is not None
        assert stored.revoked_at is not None
        assert stored.revocation_reason == reason


def test_disabled_account_cannot_login_or_use_an_existing_session(
    identity_client: TestClient,
    identity_session_factory: sessionmaker[Session],
) -> None:
    credentials = {
        "email": "investor@example.com",
        "display_name": "Investor",
        "password": "correct horse battery staple",
    }
    identity_client.post("/api/v1/auth/register", json=credentials)
    with identity_session_factory() as session:
        user = session.scalar(select(User))
        assert user is not None
        user.state = "DISABLED"
        session.commit()

    login = identity_client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    bootstrap = identity_client.get("/api/v1/auth/session")

    assert login.status_code == 401
    assert login.json()["error"]["code"] == "AUTHENTICATION_FAILED"
    assert bootstrap.status_code == 401
    with identity_session_factory() as session:
        sessions = session.scalars(select(UserSession)).all()
        assert len(sessions) == 1
        assert sessions[0].revocation_reason == "ACCOUNT_DISABLED"


def test_sixth_active_session_revokes_the_oldest(
    identity_client: TestClient,
    identity_session_factory: sessionmaker[Session],
) -> None:
    credentials = {
        "email": "investor@example.com",
        "display_name": "Investor",
        "password": "correct horse battery staple",
    }
    assert identity_client.post("/api/v1/auth/register", json=credentials).status_code == 201
    for _ in range(5):
        response = identity_client.post(
            "/api/v1/auth/login",
            json={"email": credentials["email"], "password": credentials["password"]},
        )
        assert response.status_code == 200

    with identity_session_factory() as session:
        sessions = session.scalars(
            select(UserSession).order_by(UserSession.created_at)
        ).all()

    assert len(sessions) == 6
    assert sum(stored.revoked_at is None for stored in sessions) == 5
    assert sessions[0].revocation_reason == "SESSION_LIMIT"


def test_logout_all_revokes_every_active_session(
    identity_client: TestClient,
    identity_session_factory: sessionmaker[Session],
) -> None:
    credentials = {
        "email": "investor@example.com",
        "display_name": "Investor",
        "password": "correct horse battery staple",
    }
    registration = identity_client.post("/api/v1/auth/register", json=credentials)
    identity_client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    bootstrap = identity_client.get("/api/v1/auth/session")

    response = identity_client.post(
        "/api/v1/auth/logout-all",
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": bootstrap.json()["csrf_token"],
        },
    )

    assert registration.status_code == 201
    assert response.status_code == 204
    with identity_session_factory() as session:
        sessions = session.scalars(select(UserSession)).all()
        assert len(sessions) == 3
        reasons = [stored.revocation_reason for stored in sessions]
        assert reasons.count("ROTATED") == 1
        assert reasons.count("USER_LOGOUT_ALL") == 2
