from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import SecurityAuditEvent, User, UserSession
from app.identity.security import verify_password
from app.identity.service import (
    IdentityMaintenanceUnavailable,
    register_identity,
    reset_identity_password,
)
from app.scripts.reset_password import run


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


def test_password_reset_preserves_identity_revokes_sessions_and_audits(
    identity_session_factory: sessionmaker[Session],
) -> None:
    with identity_session_factory.begin() as session:
        grant = register_identity(
            session,
            email="investor@example.com",
            display_name="Demo Investor",
            password="old correct horse battery staple",
        )
        user_id = grant.user.id
        original_role = grant.user.role
        original_state = grant.user.state

    with identity_session_factory.begin() as session:
        user, revoked_count = reset_identity_password(
            session,
            email="investor@example.com",
            password="new correct horse battery staple",
        )

    with identity_session_factory() as session:
        stored = session.get(User, user_id)
        sessions = session.scalars(
            select(UserSession).where(UserSession.user_id == user_id)
        ).all()
        event = session.scalar(
            select(SecurityAuditEvent)
            .where(SecurityAuditEvent.event_type == "IDENTITY_PASSWORD_RESET")
            .order_by(SecurityAuditEvent.id.desc())
        )

        assert user.id == user_id
        assert revoked_count == 1
        assert stored is not None
        assert stored.role == original_role
        assert stored.state == original_state
        assert not verify_password(
            stored.password_hash, "old correct horse battery staple"
        )
        assert verify_password(
            stored.password_hash, "new correct horse battery staple"
        )
        assert all(item.revoked_at is not None for item in sessions)
        assert all(
            item.revocation_reason == "OFFLINE_PASSWORD_RESET" for item in sessions
        )
        assert event is not None
        assert event.outcome == "SUCCESS"
        assert event.actor_user_id is None
        assert event.target_user_id == user_id
        assert event.event_metadata == {}


def test_password_reset_refuses_unknown_identity_without_changes(
    identity_session_factory: sessionmaker[Session],
) -> None:
    with identity_session_factory.begin() as session:
        grant = register_identity(
            session,
            email="investor@example.com",
            display_name="Demo Investor",
            password="old correct horse battery staple",
        )
        original_hash = grant.user.password_hash

    with identity_session_factory.begin() as session:
        with pytest.raises(IdentityMaintenanceUnavailable):
            reset_identity_password(
                session,
                email="missing@example.com",
                password="new correct horse battery staple",
            )

    with identity_session_factory() as session:
        stored = session.scalar(
            select(User).where(User.email == "investor@example.com")
        )
        assert stored is not None
        assert stored.password_hash == original_hash
        assert session.scalar(
            select(SecurityAuditEvent).where(
                SecurityAuditEvent.event_type == "IDENTITY_PASSWORD_RESET"
            )
        ) is None


def test_password_reset_command_refuses_mismatched_email_before_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://marketmitra_demo_user:placeholder@localhost/marketmitra_demo",
    )

    def unexpected_password_prompt(_: str) -> str:
        raise AssertionError("password prompt must not run for an unconfirmed email")

    result = run(
        [
            "--email",
            "investor@example.com",
            "--confirm-email",
            "different@example.com",
            "--confirm-database",
            "marketmitra_demo",
        ],
        password_reader=unexpected_password_prompt,
    )

    assert result == 2


def test_password_reset_command_refuses_remote_database_before_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://marketmitra_demo_user:placeholder@db.example/marketmitra_demo",
    )

    def unexpected_password_prompt(_: str) -> str:
        raise AssertionError("password prompt must not run for a remote database")

    result = run(
        [
            "--email",
            "investor@example.com",
            "--confirm-email",
            "investor@example.com",
            "--confirm-database",
            "marketmitra_demo",
        ],
        password_reader=unexpected_password_prompt,
    )

    assert result == 2
