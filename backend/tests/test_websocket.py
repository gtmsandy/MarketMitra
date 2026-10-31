"""WebSocket routing and contract tests."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Iterator

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from starlette.routing import WebSocketRoute

from app.api.routes import websocket as websocket_module
from app.main import app
from app.services.live_state import CanonicalQuote, LiveStateStore


def _registered_routes(router, prefix: str = "") -> Iterator[tuple[str, object]]:
    """Yield effective paths from FastAPI's nested router hierarchy."""
    for route in router.routes:
        path = getattr(route, "path", None)
        if path is not None:
            yield f"{prefix}{path}", route
            continue

        nested_router = getattr(route, "original_router", None)
        include_context = getattr(route, "include_context", None)
        if nested_router is not None and include_context is not None:
            yield from _registered_routes(
                nested_router,
                prefix=f"{prefix}{include_context.prefix}",
            )


def _synthetic_live_state() -> tuple[LiveStateStore, datetime]:
    store = LiveStateStore()
    observed_at = datetime(2026, 10, 30, 6, 15, tzinfo=timezone.utc)
    store.update_market(
        provider="synthetic_test",
        provider_timestamp=observed_at,
        market_status="OPEN",
        data_freshness="LIVE",
        index=2800.5,
    )
    store.update_quote(
        CanonicalQuote(
            symbol="TEST",
            ltp=105.0,
            change=5.0,
            change_percent=5.0,
            provider_timestamp=observed_at,
            ingested_at=observed_at,
        )
    )
    return store, observed_at


def test_market_websocket_is_registered_once() -> None:
    matching_routes = [
        route
        for path, route in _registered_routes(app)
        if path == "/api/v1/ws/market" and isinstance(route, WebSocketRoute)
    ]

    assert len(matching_routes) == 1


def test_market_websocket_sends_canonical_snapshot(
    client: TestClient,
    monkeypatch,
) -> None:
    store, observed_at = _synthetic_live_state()
    monkeypatch.setattr(websocket_module, "live_state_store", store)
    websocket_module.manager.active.clear()

    try:
        with client.websocket_connect("/api/v1/ws/market") as websocket:
            message = websocket.receive_json()

            assert len(websocket_module.manager.active) == 1
            assert message["type"] == "snapshot"
            assert set(message) == {"type", "data"}
            assert message["data"]["provider"] == "synthetic_test"
            assert message["data"]["market_status"] == "OPEN"
            assert message["data"]["data_freshness"] == "LIVE"
            assert message["data"]["provider_timestamp"] == observed_at.isoformat()
            assert message["data"]["quotes"]["TEST"]["symbol"] == "TEST"
            assert message["data"]["quotes"]["TEST"]["ltp"] == 105.0
    finally:
        websocket_module.manager.active.clear()


def test_production_websocket_accepts_allowed_origin(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://marketmitra.example")
    websocket_module.manager.active.clear()

    with client.websocket_connect(
        "/api/v1/ws/market", headers={"origin": "https://marketmitra.example"}
    ) as websocket:
        assert websocket.receive_json()["type"] == "snapshot"

    assert websocket_module.manager.active == set()


def test_production_websocket_rejects_disallowed_origin(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://marketmitra.example")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            "/api/v1/ws/market", headers={"origin": "https://evil.example"}
        ):
            pass

    assert exc_info.value.code == 1008


def test_production_websocket_rejects_missing_origin(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://marketmitra.example")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws/market"):
            pass

    assert exc_info.value.code == 1008


def test_development_websocket_allows_missing_origin(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")

    with client.websocket_connect("/api/v1/ws/market") as websocket:
        assert websocket.receive_json()["type"] == "snapshot"


def test_websocket_connection_cap_rejects_and_recovers(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("WEBSOCKET_MAX_CONNECTIONS", "1")
    websocket_module.manager.active.clear()

    with client.websocket_connect("/api/v1/ws/market") as first:
        assert first.receive_json()["type"] == "snapshot"
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/v1/ws/market"):
                pass
        assert exc_info.value.code == 1013

    with client.websocket_connect("/api/v1/ws/market") as recovered:
        assert recovered.receive_json()["type"] == "snapshot"


def test_market_websocket_disconnect_cleans_up_without_heartbeat_delay(
    monkeypatch,
) -> None:
    store, _ = _synthetic_live_state()
    monkeypatch.setattr(websocket_module, "live_state_store", store)

    real_sleep = asyncio.sleep

    async def yield_without_delay(_: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(
        websocket_module,
        "asyncio",
        SimpleNamespace(sleep=yield_without_delay),
    )

    class DisconnectingWebSocket:
        def __init__(self) -> None:
            self.accepted = False
            self.messages: list[dict] = []

        async def accept(self) -> None:
            self.accepted = True

        async def send_json(self, message: dict) -> None:
            if self.messages:
                raise WebSocketDisconnect()
            self.messages.append(message)

    websocket = DisconnectingWebSocket()
    websocket_module.manager.active.clear()

    asyncio.run(websocket_module.market_socket(websocket))

    assert websocket.accepted is True
    assert websocket.messages[0]["type"] == "snapshot"
    assert websocket_module.manager.active == set()


def test_unexpected_websocket_failure_is_logged_without_exception_details(
    caplog, monkeypatch
) -> None:
    class FailingWebSocket:
        async def accept(self) -> None:
            pass

        async def send_json(self, _message: dict) -> None:
            raise RuntimeError("credential=do-not-log")

    monkeypatch.setenv("APP_ENV", "development")
    websocket_module.manager.active.clear()

    with caplog.at_level("ERROR"):
        asyncio.run(websocket_module.market_socket(FailingWebSocket()))

    assert "Unexpected market WebSocket failure" in caplog.text
    assert "do-not-log" not in caplog.text
    assert websocket_module.manager.active == set()


def test_existing_http_health_endpoint_remains_registered(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["service"] == "marketmitra-api"
