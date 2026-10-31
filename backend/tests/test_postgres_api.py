"""Automated integration tests for PostgreSQL-backed API endpoints.

Validates that when MARKET_DATA_SOURCE=postgres, the FastAPI application
reads directly from PostgreSQL rather than mock data.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import _get_source
from app.main import app
from tests.postgres_ci import require_disposable_ci_database


@pytest.fixture(scope="session", autouse=True)
def disposable_postgres_only() -> None:
    require_disposable_ci_database()


@pytest.fixture
def postgres_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MARKET_DATA_SOURCE", "postgres")
    _get_source.cache_clear()
    try:
        yield TestClient(app)
    finally:
        _get_source.cache_clear()


class TestPostgresHealthApi:
    def test_health_reports_postgres_source(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["market_data_source"] == "postgres"
        assert data["database_status"] == "connected"
        assert data["last_ingestion"] is not None
        assert data["last_ingestion"]["status"] == "success"
        assert data["last_ingestion"]["prices_accepted"] >= 0


class TestPostgresMarketApi:
    def test_market_overview(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/market/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["nepse_index"] > 0
        assert data["market_status"] == "Open"
        assert "last_updated" in data

    def test_top_gainers(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/market/gainers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Verify descending sort
        percents = [item["change_percent"] for item in data]
        assert percents == sorted(percents, reverse=True)

    def test_top_losers(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/market/losers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        percents = [item["change_percent"] for item in data]
        assert percents == sorted(percents)

    def test_most_active(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/market/most-active")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        turnovers = [item["turnover"] for item in data]
        assert turnovers == sorted(turnovers, reverse=True)

    def test_market_breadth(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/market/breadth")
        assert resp.status_code == 200
        data = resp.json()
        assert data["observation_date"] == "2026-09-03"
        assert data["advancing_count"] > 0
        assert data["declining_count"] > 0
        assert data["total_count"] == data["advancing_count"] + data["declining_count"] + data["unchanged_count"]
        assert data["advance_decline_ratio"] is not None

    def test_sector_analytics(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/market/sectors")
        assert resp.status_code == 200
        data = resp.json()
        assert data == []  # Deterministic mock instruments have no sector metadata.

    def test_market_heatmap(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/market/heatmap")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 8
        assert data[0]["weight_metric"] == "turnover"


class TestPostgresStocksApi:
    def test_stocks_listing_returns_all_postgres_instruments(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/stocks")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 8

    def test_search_stocks(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/stocks", params={"q": "NABIL"})
        assert resp.status_code == 200
        data = resp.json()
        symbols = {item["symbol"] for item in data}
        assert "NABIL" in symbols

    def test_stock_detail_known_symbol(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/stocks/NABIL")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "NABIL"
        assert data["ltp"] > 0
        assert data["open"] > 0
        assert data["high"] >= data["low"]

    def test_stock_detail_unknown_symbol(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/stocks/NONEXIST123")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Stock not found"

    def test_stock_history_known_symbol(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/stocks/NABIL/history")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 180
        assert data[0]["date"] < data[-1]["date"]  # Chronological order

    def test_stock_history_unknown_symbol(self, postgres_client: TestClient) -> None:
        resp = postgres_client.get("/api/v1/stocks/NONEXIST123/history")
        assert resp.status_code == 404

    def test_stock_intraday_known_symbol_empty(self, postgres_client: TestClient) -> None:
        """Known symbol without live quotes returns an honest empty list with zero fake data."""
        resp = postgres_client.get("/api/v1/stocks/NABIL/intraday")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data == []

    def test_stock_intraday_unknown_symbol(self, postgres_client: TestClient) -> None:
        """Unknown symbol returns 404."""
        resp = postgres_client.get("/api/v1/stocks/NONEXIST123/intraday")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Stock not found"
