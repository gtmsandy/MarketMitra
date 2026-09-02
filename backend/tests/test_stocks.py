"""Tests for stock listing, search, detail, and history endpoints."""

from fastapi.testclient import TestClient


class TestStockListing:
    """GET /api/v1/stocks — list and search."""

    def test_returns_all_stocks(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 8

    def test_search_by_symbol(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks", params={"q": "NAB"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "NABIL"

    def test_search_by_company_name(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks", params={"q": "hydropower"})
        assert response.status_code == 200
        data = response.json()
        symbols = {stock["symbol"] for stock in data}
        assert "UPPER" in symbols
        assert "CHCL" in symbols

    def test_search_case_insensitive(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks", params={"q": "nica"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "NICA"

    def test_search_no_match(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks", params={"q": "ZZZZZ"})
        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestStockDetail:
    """GET /api/v1/stocks/{symbol} — single stock detail."""

    def test_valid_symbol(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks/NABIL")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "NABIL"
        assert data["company_name"] == "Nabil Bank Limited"
        assert "ltp" in data
        assert "change" in data
        assert "change_percent" in data
        assert "fifty_two_week_high" in data
        assert "fifty_two_week_low" in data
        assert data["fifty_two_week_high"] >= data["fifty_two_week_low"]

    def test_case_insensitive_symbol(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks/nabil")
        assert response.status_code == 200
        assert response.json()["symbol"] == "NABIL"

    def test_unknown_symbol_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks/NONEXIST")
        assert response.status_code == 404
        assert response.json()["detail"] == "Stock not found"


class TestStockHistory:
    """GET /api/v1/stocks/{symbol}/history — historical price data."""

    def test_returns_history(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks/NABIL/history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 180

    def test_history_point_shape(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks/NABIL/history")
        point = response.json()[0]
        assert "date" in point
        assert "open" in point
        assert "high" in point
        assert "low" in point
        assert "close" in point
        assert "volume" in point

    def test_history_ohlc_consistency(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks/NABIL/history")
        for point in response.json():
            assert point["high"] >= point["low"]
            assert point["high"] >= point["open"]
            assert point["high"] >= point["close"]
            assert point["low"] <= point["open"]
            assert point["low"] <= point["close"]
            assert point["volume"] >= 1000

    def test_history_chronological_order(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks/NABIL/history")
        dates = [point["date"] for point in response.json()]
        assert dates == sorted(dates)

    def test_history_deterministic(self, client: TestClient) -> None:
        """Two calls must return identical data (stable seed)."""
        r1 = client.get("/api/v1/stocks/NABIL/history")
        r2 = client.get("/api/v1/stocks/NABIL/history")
        assert r1.json() == r2.json()

    def test_history_unknown_symbol_returns_404(self, client: TestClient) -> None:
        response = client.get("/api/v1/stocks/NONEXIST/history")
        assert response.status_code == 404

    def test_history_no_weekends(self, client: TestClient) -> None:
        """NEPSE trades Sun–Thu; no Friday (4) or Saturday (5)."""
        from datetime import date as date_type

        response = client.get("/api/v1/stocks/NABIL/history")
        for point in response.json():
            d = date_type.fromisoformat(point["date"])
            assert d.weekday() not in (4, 5), f"{point['date']} is a NEPSE holiday"
