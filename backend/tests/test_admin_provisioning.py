from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import SecurityAuditEvent, User, UserSession
from app.identity.security import verify_password
from app.identity.service import RegistrationUnavailable, provision_admin
from app.scripts.provision_admin import EXPECTED_ALEMBIC_HEAD, run
from app.scripts.start_demo import EXPECTED_ALEMBIC_HEAD as DEMO_ALEMBIC_HEAD


def test_offline_admin_and_demo_guards_track_the_repository_migration_head() -> None:
    assert EXPECTED_ALEMBIC_HEAD == DEMO_ALEMBIC_HEAD == "0010"


@pytest.fixture
def admin_session_factory() -> Generator[sessionmaker[Session], None, None]:
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


def test_provision_admin_creates_no_session_or_default_credentials(
    admin_session_factory: sessionmaker[Session],
) -> None:
    with admin_session_factory.begin() as session:
        admin = provision_admin(
            session,
            email="admin@example.com",
            display_name="Research Administrator",
            password="correct horse battery staple",
        )

    with admin_session_factory() as session:
        stored = session.scalar(select(User))
        event = session.scalar(select(SecurityAuditEvent))
        assert stored is not None
        assert stored.id == admin.id
        assert stored.role == "ADMIN"
        assert stored.state == "ACTIVE"
        assert verify_password(stored.password_hash, "correct horse battery staple")
        assert session.scalar(select(UserSession)) is None
        assert event is not None
        assert event.event_type == "ADMIN_PROVISIONED"
        assert event.target_user_id == stored.id
        assert event.event_metadata == {}


def test_provision_admin_refuses_an_existing_identity(
    admin_session_factory: sessionmaker[Session],
) -> None:
    with admin_session_factory.begin() as session:
        provision_admin(
            session,
            email="admin@example.com",
            display_name="Research Administrator",
            password="correct horse battery staple",
        )

    with admin_session_factory() as session:
        with pytest.raises(RegistrationUnavailable):
            provision_admin(
                session,
                email="admin@example.com",
                display_name="Different Administrator",
                password="different secure password",
            )


def test_admin_command_refuses_unconfirmed_database_before_password_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://operator:placeholder@db.example/marketmitra_expected",
    )

    def unexpected_password_prompt(_: str) -> str:
        raise AssertionError("password prompt must not run for an unconfirmed database")

    result = run(
        [
            "--email",
            "admin@example.com",
            "--display-name",
            "Research Administrator",
            "--confirm-database",
            "different_database",
        ],
        password_reader=unexpected_password_prompt,
    )

    assert result == 2
