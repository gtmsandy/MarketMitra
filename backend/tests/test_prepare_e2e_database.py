"""Fail-closed contracts for the authorized E2E database preparer."""

import pytest


def test_e2e_target_requires_exact_database_role_and_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.scripts.prepare_e2e_database import E2EPreparationError, _database_url

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://marketmitra_e2e_ci_user@127.0.0.1/marketmitra_e2e_ci",
    )
    monkeypatch.setenv(
        "MARKETMITRA_E2E_CONFIRMATION",
        "marketmitra_e2e_ci/marketmitra_e2e_ci_user",
    )
    assert _database_url()[1] == "marketmitra_e2e_ci"

    monkeypatch.setenv("MARKETMITRA_E2E_CONFIRMATION", "marketmitra_fixture_ci")
    with pytest.raises(E2EPreparationError, match="confirmation"):
        _database_url()


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://marketmitra_e2e_ci_user@localhost/marketmitra_e2e_ci",
        "postgresql://marketmitra_e2e_ci_user@127.0.0.1/marketmitra_demo",
        "postgresql://postgres@127.0.0.1/marketmitra_e2e_ci",
    ],
)
def test_e2e_target_rejects_wrong_host_database_or_role(
    monkeypatch: pytest.MonkeyPatch, database_url: str
) -> None:
    from app.scripts.prepare_e2e_database import E2EPreparationError, _database_url

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv(
        "MARKETMITRA_E2E_CONFIRMATION",
        "marketmitra_e2e_ci/marketmitra_e2e_ci_user",
    )
    with pytest.raises(E2EPreparationError, match="authorized E2E target"):
        _database_url()


def test_repository_head_is_exactly_0010() -> None:
    from app.scripts.prepare_e2e_database import expected_head

    assert expected_head() == "0010"
