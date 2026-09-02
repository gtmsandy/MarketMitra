"""Tests for MARKET_DATA_SOURCE and DATABASE_URL configuration."""

import pytest


class TestMarketDataSource:
    """get_market_data_source() behaviour under different env values."""

    def test_default_resolves_to_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MARKET_DATA_SOURCE", raising=False)
        from app.core.config import get_market_data_source
        assert get_market_data_source() == "mock"

    def test_explicit_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MARKET_DATA_SOURCE", "mock")
        from app.core.config import get_market_data_source
        assert get_market_data_source() == "mock"

    def test_explicit_postgres(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MARKET_DATA_SOURCE", "postgres")
        from app.core.config import get_market_data_source
        assert get_market_data_source() == "postgres"

    def test_invalid_value_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MARKET_DATA_SOURCE", "redis")
        from app.core.config import get_market_data_source
        with pytest.raises(ValueError, match="Invalid MARKET_DATA_SOURCE"):
            get_market_data_source()

    def test_empty_string_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MARKET_DATA_SOURCE", "")
        from app.core.config import get_market_data_source
        with pytest.raises(ValueError, match="Invalid MARKET_DATA_SOURCE"):
            get_market_data_source()


class TestDatabaseUrl:
    """get_database_url() behaviour."""

    def test_returns_url_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        from app.core.config import get_database_url
        assert get_database_url() == "postgresql://user:pass@localhost/db"

    def test_missing_raises_clear_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from app.core.config import get_database_url
        with pytest.raises(ValueError, match="DATABASE_URL is required"):
            get_database_url()

    def test_empty_string_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "")
        from app.core.config import get_database_url
        with pytest.raises(ValueError, match="DATABASE_URL is required"):
            get_database_url()
