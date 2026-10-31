from datetime import datetime, timezone
from pathlib import Path
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.base import Base, make_engine, make_session_factory
from app.db.models import IngestionRun, MarketSnapshot


class TestRuntimeHealthContracts:
    def test_liveness_has_no_database_dependency(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MARKET_DATA_SOURCE", "postgres")
        monkeypatch.delenv("DATABASE_URL", raising=False)

        response = client.get("/api/v1/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "marketmitra-api"}

    def test_readiness_succeeds_with_healthy_dependencies(
        self, client: TestClient
    ) -> None:
        from app.api.routes.health import get_readiness_checker

        client.app.dependency_overrides[get_readiness_checker] = lambda: lambda: None
        try:
            response = client.get("/api/v1/health/ready")
        finally:
            client.app.dependency_overrides.pop(get_readiness_checker, None)

        assert response.status_code == 200
        assert response.json() == {"status": "ready", "service": "marketmitra-api"}

    def test_readiness_returns_503_when_database_is_unavailable(
        self, client: TestClient
    ) -> None:
        from app.api.routes.health import get_readiness_checker

        def unavailable() -> None:
            raise RuntimeError("database connection failed with secret details")

        client.app.dependency_overrides[get_readiness_checker] = lambda: unavailable
        try:
            response = client.get("/api/v1/health/ready")
        finally:
            client.app.dependency_overrides.pop(get_readiness_checker, None)

        assert response.status_code == 503
        assert response.json() == {
            "detail": {"status": "not_ready", "service": "marketmitra-api"}
        }

    def test_readiness_accepts_current_migration_revision(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from app.api.routes.health import check_runtime_readiness

        db_url = f"sqlite:///{tmp_path / 'ready.db'}"
        engine = make_engine(db_url)
        Base.metadata.create_all(engine)
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        current_head = ScriptDirectory.from_config(config).get_current_head()
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:head)"),
                {"head": current_head},
            )
        engine.dispose()

        monkeypatch.setenv("APP_ENV", "test")
        monkeypatch.setenv("MARKET_DATA_SOURCE", "postgres")
        monkeypatch.setenv("DATABASE_URL", db_url)

        check_runtime_readiness()

    def test_readiness_rejects_stale_migration_revision(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from app.api.routes.health import check_runtime_readiness

        db_url = f"sqlite:///{tmp_path / 'stale.db'}"
        engine = make_engine(db_url)
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
            connection.execute(
                text("INSERT INTO alembic_version (version_num) VALUES ('0001')")
            )
        engine.dispose()

        monkeypatch.setenv("APP_ENV", "test")
        monkeypatch.setenv("MARKET_DATA_SOURCE", "postgres")
        monkeypatch.setenv("DATABASE_URL", db_url)

        with pytest.raises(RuntimeError, match="migration revision"):
            check_runtime_readiness()


class TestHealthEndpoint:
    def test_mock_provider_returns_not_configured(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MARKET_DATA_SOURCE", "mock")
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "marketmitra-api"
        assert data["market_data_source"] == "mock"
        assert data["database_status"] == "not_configured"
        assert data["market_status"] in ("OPEN", "CLOSED")
        assert data["data_freshness"] in ("FRESH", "STALE", "UNKNOWN")
        assert data["last_ingestion"] is None

    def test_connected_postgres_health(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        db_path = tmp_path / "health_connected.db"
        db_url = f"sqlite:///{db_path}"
        engine = make_engine(db_url)
        Base.metadata.create_all(engine)

        monkeypatch.setenv("MARKET_DATA_SOURCE", "postgres")
        monkeypatch.setenv("DATABASE_URL", db_url)

        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "marketmitra-api"
        assert data["market_data_source"] == "postgres"
        assert data["database_status"] == "connected"
        assert data["market_status"] in ("OPEN", "CLOSED")
        assert data["data_freshness"] == "UNKNOWN"
        assert data["last_ingestion"] is None

    def test_connected_postgres_with_snapshot_and_ingestion(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        db_path = tmp_path / "health_seeded.db"
        db_url = f"sqlite:///{db_path}"
        engine = make_engine(db_url)
        Base.metadata.create_all(engine)

        factory = make_session_factory(db_url)
        with factory() as session:
            now = datetime.now(tz=timezone.utc)
            snapshot = MarketSnapshot(
                nepse_index=2786.42,
                index_change=21.35,
                index_change_percent=0.77,
                turnover=552_907_933.0,
                total_volume=1_241_890,
                total_transactions=38_640,
                market_status="Open",
                captured_at=now,
            )
            run = IngestionRun(
                source="mock",
                started_at=now,
                finished_at=now,
                status="success",
                instruments_upserted=8,
                snapshots_inserted=1,
                snapshots_skipped=0,
                prices_accepted=100,
                prices_skipped=0,
                prices_replaced=0,
                prices_rejected=0,
            )
            session.add(snapshot)
            session.add(run)
            session.commit()

        monkeypatch.setenv("MARKET_DATA_SOURCE", "postgres")
        monkeypatch.setenv("DATABASE_URL", db_url)

        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database_status"] == "connected"
        assert data["data_freshness"] in ("FRESH", "STALE")
        assert data["last_ingestion"] is not None
        assert data["last_ingestion"]["source"] == "mock"
        assert data["last_ingestion"]["status"] == "success"
        assert data["last_ingestion"]["prices_accepted"] == 100

    def test_unreachable_postgres_returns_degraded(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MARKET_DATA_SOURCE", "postgres")
        # Non-routable IP/port ensures connection failure
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:pass@127.0.0.1:59999/nonexistent"
        )

        response = client.get("/api/v1/health")
        # Must return HTTP 200, not an unhandled 500 error
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["service"] == "marketmitra-api"
        assert data["market_data_source"] == "postgres"
        assert data["database_status"] == "disconnected"
        assert data["data_freshness"] == "UNKNOWN"
        assert data["last_ingestion"] is None

    def test_missing_database_url_returns_degraded(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MARKET_DATA_SOURCE", "postgres")
        monkeypatch.delenv("DATABASE_URL", raising=False)

        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database_status"] == "disconnected"
