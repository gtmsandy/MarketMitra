import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.api.dependencies import _get_source
    monkeypatch.setenv("MARKET_DATA_SOURCE", "mock")
    _get_source.cache_clear()
    try:
        yield TestClient(app)
    finally:
        _get_source.cache_clear()
