"""Database engine reliability contracts without external connections."""

import pytest
from sqlalchemy import text

from app.db.base import make_engine


def test_sqlite_engine_remains_compatible() -> None:
    engine = make_engine("sqlite:///:memory:")
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()


def test_postgres_engine_uses_bounded_pool_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DB_POOL_SIZE", "4")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "2")
    monkeypatch.setenv("DB_POOL_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("DB_POOL_RECYCLE_SECONDS", "300")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_SECONDS", "3")

    engine = make_engine("postgresql://user:secret@db.example.com/marketmitra")
    try:
        assert engine.pool.size() == 4
        assert engine.pool._max_overflow == 2
        assert engine.pool._timeout == 7
        assert engine.pool._recycle == 300
        assert engine.pool._pre_ping is True
        assert engine.url.query["connect_timeout"] == "3"
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "variable, value",
    [
        ("DB_POOL_SIZE", "0"),
        ("DB_MAX_OVERFLOW", "101"),
        ("DB_POOL_TIMEOUT_SECONDS", "0"),
        ("DB_POOL_RECYCLE_SECONDS", "-1"),
        ("DB_CONNECT_TIMEOUT_SECONDS", "61"),
    ],
)
def test_invalid_pool_configuration_fails_closed(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValueError, match=variable):
        make_engine("postgresql://user:secret@db.example.com/marketmitra")
