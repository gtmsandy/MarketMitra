"""Fail-closed contracts for the disposable PostgreSQL integration database."""

import pytest

from tests.postgres_ci import require_disposable_ci_database


def test_disposable_ci_database_accepts_confirmed_local_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql://ci_user:ci_password@127.0.0.1:5432/marketmitra_ci"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("MARKETMITRA_CONFIRM_DISPOSABLE", "marketmitra_ci")

    assert require_disposable_ci_database() == url


@pytest.mark.parametrize(
    ("url", "confirmation", "message"),
    [
        ("", "", "DATABASE_URL is required"),
        ("sqlite:///marketmitra_ci", "marketmitra_ci", "PostgreSQL URL"),
        (
            "postgresql://ci:ci@database.example/marketmitra_ci",
            "marketmitra_ci",
            "runner-local host",
        ),
        (
            "postgresql://ci:ci@127.0.0.1/marketmitra",
            "marketmitra",
            "must end in _ci",
        ),
        (
            "postgresql://ci:ci@127.0.0.1/marketmitra_ci",
            "wrong_database",
            "must exactly match",
        ),
    ],
)
def test_disposable_ci_database_rejects_unsafe_configuration(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    confirmation: str,
    message: str,
) -> None:
    if url:
        monkeypatch.setenv("DATABASE_URL", url)
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    if confirmation:
        monkeypatch.setenv("MARKETMITRA_CONFIRM_DISPOSABLE", confirmation)
    else:
        monkeypatch.delenv("MARKETMITRA_CONFIRM_DISPOSABLE", raising=False)

    with pytest.raises(RuntimeError, match=message):
        require_disposable_ci_database()
