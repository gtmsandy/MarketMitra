from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def make_engine(database_url: str):
    """Create a SQLAlchemy engine for the given URL.

    connect_args is only applied for SQLite to allow cross-thread use in tests.
    """
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, connect_args=connect_args)


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
