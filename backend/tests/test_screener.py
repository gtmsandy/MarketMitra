from fastapi.testclient import TestClient


def test_screener_returns_common_session_metadata_and_total(client: TestClient) -> None:
    response = client.get("/api/v1/stocks/screener", params={"page_size": 3})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 8
    assert len(data["items"]) == 3
    assert data["observation_policy"] == "COMMON_MARKET_SESSION"
    assert data["observation_date"] == "2026-09-03"


def test_screener_filters_search_sector_and_numeric_ranges(client: TestClient) -> None:
    response = client.get(
        "/api/v1/stocks/screener",
        params={
            "q": "bank",
            "sector": "commercial banks",
            "min_price": 500,
            "max_change_percent": 3,
            "min_volume": 150_000,
        },
    )

    assert response.status_code == 200
    assert [item["symbol"] for item in response.json()["items"]] == ["NABIL"]


def test_screener_sorts_descending_with_symbol_tiebreaker(client: TestClient) -> None:
    response = client.get(
        "/api/v1/stocks/screener",
        params={"sort_by": "change_percent", "sort_order": "desc", "page_size": 20},
    )

    assert response.status_code == 200
    rows = response.json()["items"]
    assert [row["symbol"] for row in rows[:3]] == ["CHCL", "NABIL", "GBIME"]
    assert [row["change_percent"] for row in rows] == sorted(
        (row["change_percent"] for row in rows), reverse=True
    )


def test_screener_paginates_deterministically(client: TestClient) -> None:
    first = client.get("/api/v1/stocks/screener", params={"page": 2, "page_size": 2, "sort_by": "symbol"})
    second = client.get("/api/v1/stocks/screener", params={"page": 2, "page_size": 2, "sort_by": "symbol"})

    assert first.status_code == 200
    assert first.json() == second.json()
    assert [row["symbol"] for row in first.json()["items"]] == ["NABIL", "NICA"]
    assert first.json()["total"] == 8


def test_screener_rejects_invalid_ranges_and_sorting(client: TestClient) -> None:
    invalid_range = client.get(
        "/api/v1/stocks/screener",
        params={"min_price": 100, "max_price": 10},
    )
    invalid_sort = client.get(
        "/api/v1/stocks/screener",
        params={"sort_by": "pe_ratio"},
    )

    assert invalid_range.status_code == 422
    assert invalid_sort.status_code == 422


def test_screener_empty_results_are_explicit(client: TestClient) -> None:
    response = client.get("/api/v1/stocks/screener", params={"q": "not-a-symbol"})

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0
