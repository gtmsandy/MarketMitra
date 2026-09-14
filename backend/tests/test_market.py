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


class TestMarketBreadth:
    """GET /api/v1/market/breadth — market advance/decline metrics."""

    def test_breadth_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/v1/market/breadth")
        assert resp.status_code == 200
        data = resp.json()
        assert "observation_date" in data
        assert "advancing_count" in data
        assert "declining_count" in data
        assert "unchanged_count" in data
        assert "total_count" in data
        assert "advance_decline_ratio" in data

    def test_breadth_counts_sum_to_total(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/breadth").json()
        total = data["total_count"]
        assert data["advancing_count"] + data["declining_count"] + data["unchanged_count"] == total

    def test_breadth_percentages_sum_to_100(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/breadth").json()
        pct_sum = round(data["advancing_percent"] + data["declining_percent"] + data["unchanged_percent"], 1)
        assert pct_sum in (99.9, 100.0, 100.1)


class TestSectorAnalytics:
    """GET /api/v1/market/sectors — sector aggregate performance."""

    def test_sectors_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/v1/market/sectors")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_sector_fields_and_methodology(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/sectors").json()
        for item in data:
            assert "sector" in item
            assert item["stock_count"] > 0
            assert item["advancing_count"] + item["declining_count"] + item["unchanged_count"] == item["stock_count"]
            assert "average_change_percent" in item
            assert item["methodology"] == "equal_weighted_constituent_daily_percentage_change"

    def test_sectors_sorted_descending(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/sectors").json()
        avg_changes = [item["average_change_percent"] for item in data]
        assert avg_changes == sorted(avg_changes, reverse=True)


class TestMarketHeatmap:
    """GET /api/v1/market/heatmap — market heatmap equity items."""

    def test_heatmap_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/v1/market/heatmap")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_heatmap_item_shape(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/heatmap").json()
        first = data[0]
        assert "symbol" in first
        assert "company_name" in first
        assert "ltp" in first
        assert "change_percent" in first
        assert "volume" in first
        assert "turnover" in first
        assert "observation_date" in first
        assert first["weight_metric"] == "turnover"

    def test_heatmap_sorted_by_turnover_descending(self, client: TestClient) -> None:
        data = client.get("/api/v1/market/heatmap").json()
        turnovers = [item["turnover"] for item in data]
        assert turnovers == sorted(turnovers, reverse=True)
