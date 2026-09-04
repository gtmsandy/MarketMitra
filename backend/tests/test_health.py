from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.db.base import Base, make_engine, make_session_factory
from app.db.models import IngestionRun, MarketSnapshot


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
