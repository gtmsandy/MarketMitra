"""Safety contracts for the opt-in PostgreSQL benchmark runner."""

import pytest

from tests.postgres_performance_benchmark import _validated_database_url


def test_benchmark_requires_an_explicit_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MARKETMITRA_BENCHMARK_DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="is required"):
        _validated_database_url()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:example@localhost:5432/marketmitra",
        "postgresql://user:example@example.com:5432/marketmitra_benchmark",
        "sqlite:///marketmitra_benchmark.db",
    ],
)
def test_benchmark_rejects_unsafe_targets(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("MARKETMITRA_BENCHMARK_DATABASE_URL", url)
    monkeypatch.setenv("MARKETMITRA_CONFIRM_DISPOSABLE", "marketmitra_benchmark")

    with pytest.raises(RuntimeError):
        _validated_database_url()


def test_benchmark_requires_database_name_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MARKETMITRA_BENCHMARK_DATABASE_URL",
        "postgresql://user:example@localhost:5432/marketmitra_benchmark",
    )
    monkeypatch.setenv("MARKETMITRA_CONFIRM_DISPOSABLE", "different_database")

    with pytest.raises(RuntimeError, match="exactly match"):
        _validated_database_url()


def test_benchmark_accepts_explicitly_confirmed_local_disposable_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql://user:example@localhost:5432/marketmitra_benchmark"
    monkeypatch.setenv("MARKETMITRA_BENCHMARK_DATABASE_URL", url)
    monkeypatch.setenv("MARKETMITRA_CONFIRM_DISPOSABLE", "marketmitra_benchmark")

    assert _validated_database_url() == url
