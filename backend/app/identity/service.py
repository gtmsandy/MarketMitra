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
    verifier_matches,
    verify_password,
)

SESSION_IDLE_DURATION = timedelta(minutes=30)
SESSION_ABSOLUTE_DURATION = timedelta(hours=12)
MAX_ACTIVE_SESSIONS = 5

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


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _revoke(identity_session: UserSession, now: datetime, reason: str) -> None:
    if identity_session.revoked_at is None:
        identity_session.revoked_at = now
        identity_session.revocation_reason = reason


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
    session.execute(select(User.id).where(User.id == user.id).with_for_update())
    active_sessions = session.scalars(
        select(UserSession)
        .where(
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
            UserSession.idle_expires_at > now,
            UserSession.absolute_expires_at > now,
        )
        .order_by(UserSession.created_at, UserSession.id)
        .with_for_update()
    ).all()
    sessions_to_revoke = max(0, len(active_sessions) - MAX_ACTIVE_SESSIONS + 1)
    for oldest in active_sessions[:sessions_to_revoke]:
        _revoke(oldest, now, "SESSION_LIMIT")

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


def resolve_session(
    session: Session, session_token: str | None, *, rotate_csrf: bool
) -> SessionGrant | None:
    if not session_token:
        return None

    try:
        token_verifier = digest_secret(session_token)
    except UnicodeEncodeError:
        return None

    identity_session = session.scalar(
        select(UserSession).where(
            UserSession.token_verifier == token_verifier
        ).with_for_update()
    )
    if identity_session is None or identity_session.revoked_at is not None:
        return None

    now = _now()
    user = identity_session.user
    reason: str | None = None
    if user.state != "ACTIVE":
        reason = "ACCOUNT_DISABLED"
    elif _as_utc(identity_session.absolute_expires_at) <= now:
        reason = "ABSOLUTE_EXPIRED"
    elif _as_utc(identity_session.idle_expires_at) <= now:
        reason = "IDLE_EXPIRED"

    if reason is not None:
        _revoke(identity_session, now, reason)
        _audit(
            session,
            "SESSION_REJECTED",
            "DENIED",
            actor_user=user,
            identity_session=identity_session,
        )
        return None

    identity_session.last_activity_at = now
    identity_session.idle_expires_at = min(
        now + SESSION_IDLE_DURATION,
        _as_utc(identity_session.absolute_expires_at),
    )
    csrf_token = generate_secret() if rotate_csrf else ""
    if rotate_csrf:
        identity_session.csrf_verifier = digest_secret(csrf_token)
    return SessionGrant(user, identity_session, session_token, csrf_token)


def rotate_session(session: Session, grant: SessionGrant) -> SessionGrant:
    # Reuse the validation timestamp so expiry cannot race the rotation write.
    now = _as_utc(grant.session.last_activity_at)
    _revoke(grant.session, now, "ROTATED")
    session_token = generate_secret()
    csrf_token = generate_secret()
    absolute_expires_at = _as_utc(grant.session.absolute_expires_at)
    successor = UserSession(
        user=grant.user,
        token_verifier=digest_secret(session_token),
        csrf_verifier=digest_secret(csrf_token),
        created_at=now,
        last_activity_at=now,
        idle_expires_at=min(now + SESSION_IDLE_DURATION, absolute_expires_at),
        absolute_expires_at=absolute_expires_at,
        rotation_predecessor_id=grant.session.id,
    )
    session.add(successor)
    session.flush()
    _audit(
        session,
        "SESSION_ROTATED",
        "SUCCESS",
        actor_user=grant.user,
        identity_session=successor,
    )
    return SessionGrant(grant.user, successor, session_token, csrf_token)


def csrf_matches(identity_session: UserSession, candidate: str | None) -> bool:
    return bool(candidate) and verifier_matches(
        identity_session.csrf_verifier, candidate or ""
    )


def logout_session(session: Session, grant: SessionGrant) -> None:
    now = _now()
    _revoke(grant.session, now, "USER_LOGOUT")
    _audit(
        session,
        "IDENTITY_LOGOUT",
        "SUCCESS",
        actor_user=grant.user,
        identity_session=grant.session,
    )


def logout_all_sessions(session: Session, grant: SessionGrant) -> None:
    now = _now()
    active_sessions = session.scalars(
        select(UserSession)
        .where(
            UserSession.user_id == grant.user.id,
            UserSession.revoked_at.is_(None),
        )
        .with_for_update()
    ).all()
    for active_session in active_sessions:
        _revoke(active_session, now, "USER_LOGOUT_ALL")
    _audit(
        session,
        "IDENTITY_LOGOUT_ALL",
        "SUCCESS",
        actor_user=grant.user,
        identity_session=grant.session,
    )
