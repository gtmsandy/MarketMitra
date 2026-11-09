from sqlalchemy import CheckConstraint, LargeBinary, UniqueConstraint, create_engine, inspect

from app.db.base import Base
from app.db.models import SecurityAuditEvent, User, UserSession, Watchlist, WatchlistItem


def test_identity_tables_create_with_expected_columns() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        inspector = inspect(engine)

        assert {column["name"] for column in inspector.get_columns("users")} == {
            "id",
            "email",
            "display_name",
            "password_hash",
            "role",
            "state",
            "created_at",
            "updated_at",
            "password_changed_at",
        }
        assert {column["name"] for column in inspector.get_columns("sessions")} == {
            "id",
            "user_id",
            "token_verifier",
            "csrf_verifier",
            "created_at",
            "last_activity_at",
            "idle_expires_at",
            "absolute_expires_at",
            "revoked_at",
            "revocation_reason",
            "rotation_predecessor_id",
        }
        assert {
            column["name"] for column in inspector.get_columns("security_audit_events")
        } == {
            "id",
            "event_type",
            "outcome",
            "actor_user_id",
            "target_user_id",
            "session_id",
            "request_id",
            "metadata",
            "created_at",
        }
    finally:
        engine.dispose()


def test_user_role_state_and_normalized_email_are_database_constrained() -> None:
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in User.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    uniques = {
        constraint.name
        for constraint in User.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert "ck_users_email_normalized" in checks
    assert "ck_users_role" in checks
    assert "ck_users_state" in checks
    assert "uq_users_email" in uniques


def test_session_schema_stores_only_fixed_length_secret_verifiers() -> None:
    token_type = UserSession.__table__.c.token_verifier.type
    csrf_type = UserSession.__table__.c.csrf_verifier.type

    assert isinstance(token_type, LargeBinary)
    assert token_type.length == 32
    assert isinstance(csrf_type, LargeBinary)
    assert csrf_type.length == 32
    assert "token" not in UserSession.__table__.c
    assert "csrf_token" not in UserSession.__table__.c


def test_session_lifetimes_and_revocation_metadata_are_constrained() -> None:
    checks = {
        constraint.name
        for constraint in UserSession.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert checks >= {
        "ck_sessions_expiration_order",
        "ck_sessions_activity_window",
        "ck_sessions_revocation_pair",
    }


def test_audit_schema_contains_no_secret_or_password_fields() -> None:
    columns = set(SecurityAuditEvent.__table__.c.keys())

    assert not columns.intersection(
        {"password", "password_hash", "token", "token_verifier", "csrf_token", "csrf_verifier"}
    )


def test_watchlist_schema_enforces_owner_and_instrument_uniqueness() -> None:
    watchlist_uniques = {
        constraint.name
        for constraint in Watchlist.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    item_uniques = {
        constraint.name
        for constraint in WatchlistItem.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert "uq_watchlists_owner_name" in watchlist_uniques
    assert "uq_watchlist_items_watchlist_symbol" in item_uniques
    assert "ck_watchlists_name_normalized" in {
        constraint.name
        for constraint in Watchlist.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
