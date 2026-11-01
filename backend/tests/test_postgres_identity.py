"""PostgreSQL-only identity migration integrity tests."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_database_url
from app.db.base import make_session_factory
from app.identity.service import register_identity, resolve_session
from tests.postgres_ci import require_disposable_ci_database


@pytest.fixture(scope="session", autouse=True)
def disposable_postgres_only() -> None:
    require_disposable_ci_database()


def test_identity_migration_created_all_tables() -> None:
    engine = create_engine(get_database_url())
    try:
        tables = set(inspect(engine).get_table_names())
        assert {"users", "sessions", "security_audit_events"} <= tables
    finally:
        engine.dispose()


def test_security_audit_events_reject_updates() -> None:
    engine = create_engine(get_database_url())
    connection = engine.connect()
    try:
        request_id = uuid4()
        with connection.begin():
            event_id = connection.execute(
                text(
                    """
                    insert into security_audit_events
                        (event_type, outcome, request_id, metadata)
                    values
                        ('MIGRATION_TEST', 'SUCCESS', :request_id, '{}'::jsonb)
                    returning id
                    """
                ),
                {"request_id": request_id},
            ).scalar_one()

        transaction = connection.begin()
        try:
            with pytest.raises(DBAPIError, match="append-only"):
                connection.execute(
                    text(
                        "update security_audit_events "
                        "set outcome = 'FAILURE' where id = :event_id"
                    ),
                    {"event_id": event_id},
                )
        finally:
            transaction.rollback()
    finally:
        connection.close()
        engine.dispose()


def test_identity_session_lifecycle_uses_postgresql_constraints() -> None:
    factory = make_session_factory(get_database_url())
    email = f"identity-{uuid4()}@example.com"
    with factory.begin() as session:
        grant = register_identity(
            session,
            email=email,
            display_name="PostgreSQL Identity",
            password="correct horse battery staple",
        )
        session_token = grant.session_token

    with factory.begin() as session:
        resolved = resolve_session(session, session_token, rotate_csrf=True)

        assert resolved is not None
        assert resolved.user.email == email
        assert resolved.csrf_token
