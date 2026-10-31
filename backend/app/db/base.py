from collections.abc import Generator
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def _bounded_integer(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def make_engine(database_url: str):
    """Create a SQLAlchemy engine for the given URL.

    connect_args is only applied for SQLite to allow cross-thread use in tests.
    """
    if database_url.startswith("sqlite"):
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
        )

    url = make_url(database_url)
    connect_timeout = _bounded_integer(
        "DB_CONNECT_TIMEOUT_SECONDS", 5, 1, 60
    )
    url = url.update_query_dict({"connect_timeout": str(connect_timeout)})
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=_bounded_integer("DB_POOL_SIZE", 5, 1, 50),
        max_overflow=_bounded_integer("DB_MAX_OVERFLOW", 5, 0, 100),
        pool_timeout=_bounded_integer("DB_POOL_TIMEOUT_SECONDS", 10, 1, 60),
        pool_recycle=_bounded_integer(
            "DB_POOL_RECYCLE_SECONDS", 1800, 0, 86400
        ),
    )


def make_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = make_engine(database_url)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    """Yield a request-scoped database session and guarantee cleanup.

    Intended for use as a FastAPI dependency via functools.partial or a closure.
    """
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
