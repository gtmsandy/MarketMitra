"""Tests for market overview and rankings endpoints."""

from fastapi.testclient import TestClient


class TestMarketOverview:
    """GET /api/v1/market/overview"""

    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/v1/market/overview")
        assert response.status_code == 200

    def test_response_shape(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/overview").json()
        assert "nepse_index" in data
        assert "index_change" in data
        assert "index_change_percent" in data
        assert "turnover" in data
        assert "total_volume" in data
        assert "total_transactions" in data
        assert "market_status" in data
        assert "last_updated" in data

    def test_values_are_reasonable(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/overview").json()
        assert data["nepse_index"] > 0
        assert data["turnover"] > 0
        assert data["total_volume"] > 0
        assert data["total_transactions"] > 0
        assert isinstance(data["market_status"], str)
        assert len(data["market_status"]) > 0


class TestTopGainers:
    """GET /api/v1/market/gainers"""

    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/v1/market/gainers")
        assert response.status_code == 200

    def test_response_shape(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/gainers").json()
        assert isinstance(data, list)
        assert len(data) > 0
        for item in data:
            assert "symbol" in item
            assert "company_name" in item
            assert "ltp" in item
            assert "change_percent" in item
            assert "volume" in item

    def test_all_positive_change(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/gainers").json()
        for item in data:
            assert item["change_percent"] > 0, (
                f"{item['symbol']} has non-positive change_percent {item['change_percent']}"
            )

    def test_sorted_descending(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/gainers").json()
        percents = [item["change_percent"] for item in data]
        assert percents == sorted(percents, reverse=True)


class TestTopLosers:
    """GET /api/v1/market/losers"""

    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/v1/market/losers")
        assert response.status_code == 200

    def test_response_shape(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/losers").json()
        assert isinstance(data, list)
        assert len(data) > 0
        for item in data:
            assert "symbol" in item
            assert "company_name" in item
            assert "ltp" in item
            assert "change_percent" in item
            assert "volume" in item

    def test_all_negative_change(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/losers").json()
        for item in data:
            assert item["change_percent"] < 0, (
                f"{item['symbol']} has non-negative change_percent {item['change_percent']}"
            )

    def test_sorted_ascending(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/losers").json()
        percents = [item["change_percent"] for item in data]
        assert percents == sorted(percents)


class TestMostActive:
    """GET /api/v1/market/most-active"""

    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/v1/market/most-active")
        assert response.status_code == 200

    def test_response_shape(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/most-active").json()
        assert isinstance(data, list)
        assert len(data) > 0
        for item in data:
            assert "symbol" in item
            assert "company_name" in item
            assert "ltp" in item
            assert "volume" in item
            assert "turnover" in item

    def test_sorted_by_turnover_descending(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/most-active").json()
        turnovers = [item["turnover"] for item in data]
        assert turnovers == sorted(turnovers, reverse=True)
