"""Tests for MARKET_DATA_SOURCE and DATABASE_URL configuration."""

import pytest


def _set_valid_production_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MARKET_DATA_SOURCE", "postgres")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://marketmitra:secret@db.example.com/marketmitra?sslmode=require",
    )
    monkeypatch.setenv("CORS_ORIGINS", "https://marketmitra.example")
    monkeypatch.setenv("TRUSTED_HOSTS", "api.marketmitra.example")
    monkeypatch.setenv("LIVE_MARKET_ENABLED", "false")


class TestApplicationEnvironment:
    def test_development_defaults_remain_valid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.delenv("MARKET_DATA_SOURCE", raising=False)
        monkeypatch.delenv("CORS_ORIGINS", raising=False)

        from app.core.config import get_application_environment, validate_runtime_config

        assert get_application_environment() == "development"
        validate_runtime_config()

    def test_valid_explicit_production_configuration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_valid_production_environment(monkeypatch)

        from app.core.config import validate_runtime_config

        validate_runtime_config()

    @pytest.mark.parametrize("value", ["", "staging", "prod"])
    def test_invalid_application_environment_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        monkeypatch.setenv("APP_ENV", value)

        from app.core.config import get_application_environment

        with pytest.raises(ValueError, match="Invalid APP_ENV"):
            get_application_environment()

    def test_production_rejects_missing_database_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_valid_production_environment(monkeypatch)
        monkeypatch.delenv("DATABASE_URL")

        from app.core.config import validate_runtime_config

        with pytest.raises(ValueError, match="DATABASE_URL"):
            validate_runtime_config()

    def test_production_rejects_implicit_mock_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_valid_production_environment(monkeypatch)
        monkeypatch.setenv("MARKET_DATA_SOURCE", "mock")

        from app.core.config import validate_runtime_config

        with pytest.raises(ValueError, match="MARKET_DATA_SOURCE=postgres"):
            validate_runtime_config()

    def test_production_requires_explicit_frontend_origins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_valid_production_environment(monkeypatch)
        monkeypatch.delenv("CORS_ORIGINS")

        from app.core.config import validate_runtime_config

        with pytest.raises(ValueError, match="CORS_ORIGINS"):
            validate_runtime_config()

    @pytest.mark.parametrize("trusted_hosts", [None, "", "*"])
    def test_production_requires_explicit_non_wildcard_trusted_hosts(
        self, monkeypatch: pytest.MonkeyPatch, trusted_hosts: str | None
    ) -> None:
        _set_valid_production_environment(monkeypatch)
        if trusted_hosts is None:
            monkeypatch.delenv("TRUSTED_HOSTS")
        else:
            monkeypatch.setenv("TRUSTED_HOSTS", trusted_hosts)

        from app.core.config import validate_runtime_config

        with pytest.raises(ValueError, match="TRUSTED_HOSTS"):
            validate_runtime_config()

    def test_production_rejects_hsts_without_https_deployment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_valid_production_environment(monkeypatch)
        monkeypatch.setenv("HSTS_ENABLED", "true")
        monkeypatch.setenv("HTTPS_DEPLOYMENT", "false")

        from app.core.config import validate_runtime_config

        with pytest.raises(ValueError, match="HTTPS_DEPLOYMENT=true"):
            validate_runtime_config()

    @pytest.mark.parametrize(
        "database_url, message",
        [
            (
                "postgresql://marketmitra:secret@localhost/marketmitra?sslmode=require",
                "remote database host",
            ),
            (
                "postgresql://user:password@db.example.com/marketmitra?sslmode=require",
                "placeholder database credentials",
            ),
            (
                "postgresql://marketmitra:secret@db.example.com/marketmitra",
                "encrypted database connection",
            ),
            ("sqlite:///marketmitra.db", "PostgreSQL DATABASE_URL"),
        ],
    )
    def test_production_rejects_unsafe_database_urls(
        self,
        monkeypatch: pytest.MonkeyPatch,
        database_url: str,
        message: str,
    ) -> None:
        _set_valid_production_environment(monkeypatch)
        monkeypatch.setenv("DATABASE_URL", database_url)

        from app.core.config import validate_runtime_config

        with pytest.raises(ValueError, match=message):
            validate_runtime_config()

    def test_production_rejects_replay_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_valid_production_environment(monkeypatch)
        monkeypatch.setenv("LIVE_MARKET_ENABLED", "true")
        monkeypatch.setenv("LIVE_MARKET_PROVIDER", "replay")

        from app.core.config import validate_runtime_config

        with pytest.raises(ValueError, match="replay"):
            validate_runtime_config()

    def test_production_live_polling_requires_explicit_authorization(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_valid_production_environment(monkeypatch)
        monkeypatch.setenv("LIVE_MARKET_ENABLED", "true")
        monkeypatch.setenv("LIVE_MARKET_PROVIDER", "external")
        monkeypatch.setenv("NEPSE_PROVIDER_NAME", "licensed-provider")
        monkeypatch.setenv("NEPSE_LIVE_API_URL", "https://feed.example.com")
        monkeypatch.delenv("LIVE_MARKET_AUTHORIZED", raising=False)

        from app.core.config import validate_runtime_config

        with pytest.raises(ValueError, match="explicit authorization"):
            validate_runtime_config()

    def test_production_accepts_deliberately_authorized_live_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _set_valid_production_environment(monkeypatch)
        monkeypatch.setenv("LIVE_MARKET_ENABLED", "true")
        monkeypatch.setenv("LIVE_MARKET_PROVIDER", "external")
        monkeypatch.setenv("LIVE_MARKET_AUTHORIZED", "true")
        monkeypatch.setenv("NEPSE_PROVIDER_NAME", "licensed-provider")
        monkeypatch.setenv("NEPSE_LIVE_API_URL", "https://feed.example.com")

        from app.core.config import validate_runtime_config

        validate_runtime_config()

    def test_application_startup_rejects_invalid_production_configuration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi.testclient import TestClient

        from app.main import app

        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("MARKET_DATA_SOURCE", "mock")

        with pytest.raises(ValueError, match="MARKET_DATA_SOURCE=postgres"):
            with TestClient(app):
                pass


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
