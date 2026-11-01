"""Transactional identity registration, login, and session creation."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import SecurityAuditEvent, User, UserSession
from app.identity.security import (
    digest_secret,
    generate_secret,
    hash_password,
    password_needs_rehash,
    verify_password,
)

SESSION_IDLE_DURATION = timedelta(minutes=30)
SESSION_ABSOLUTE_DURATION = timedelta(hours=12)

# Public, non-credential verifier equalizes unknown-account password work.
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "sGwuBF2X4aiXvqZAMSsWEQ$"
    "t1+zTbKGgYBKqD2XEnppmGy2oKIBuD0YmAlQEPqNhMA"
)


class RegistrationUnavailable(Exception):
    """The requested identity cannot be registered."""


@dataclass(frozen=True)
class SessionGrant:
    user: User
    session: UserSession
    session_token: str
    csrf_token: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(
    session: Session,
    event_type: str,
    outcome: str,
    *,
    actor_user: User | None = None,
    identity_session: UserSession | None = None,
) -> None:
    session.add(
        SecurityAuditEvent(
            event_type=event_type,
            outcome=outcome,
            actor_user_id=actor_user.id if actor_user else None,
            target_user_id=actor_user.id if actor_user else None,
            session_id=identity_session.id if identity_session else None,
            event_metadata={},
        )
    )


def _create_session(session: Session, user: User, now: datetime) -> SessionGrant:
    session_token = generate_secret()
    csrf_token = generate_secret()
    identity_session = UserSession(
        user=user,
        token_verifier=digest_secret(session_token),
        csrf_verifier=digest_secret(csrf_token),
        created_at=now,
        last_activity_at=now,
        idle_expires_at=now + SESSION_IDLE_DURATION,
        absolute_expires_at=now + SESSION_ABSOLUTE_DURATION,
    )
    session.add(identity_session)
    session.flush()
    return SessionGrant(user, identity_session, session_token, csrf_token)


def register_identity(
    session: Session, *, email: str, display_name: str, password: str
) -> SessionGrant:
    now = _now()
    user = User(
        email=email,
        display_name=display_name,
        password_hash=hash_password(password),
        role="USER",
        state="ACTIVE",
        created_at=now,
        updated_at=now,
        password_changed_at=now,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        raise RegistrationUnavailable from exc

    grant = _create_session(session, user, now)
    _audit(
        session,
        "IDENTITY_REGISTERED",
        "SUCCESS",
        actor_user=user,
        identity_session=grant.session,
    )
    return grant


def authenticate_identity(
    session: Session, *, email: str, password: str
) -> SessionGrant | None:
    user = session.scalar(select(User).where(User.email == email))
    password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(password_hash, password)

    if user is None or not password_matches or user.state != "ACTIVE":
        _audit(session, "IDENTITY_LOGIN", "FAILURE", actor_user=user)
        return None

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        user.password_changed_at = _now()

    grant = _create_session(session, user, _now())
    _audit(
        session,
        "IDENTITY_LOGIN",
        "SUCCESS",
        actor_user=user,
        identity_session=grant.session,
    )
    return grant
