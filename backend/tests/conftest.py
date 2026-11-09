import pytest
from fastapi.testclient import TestClient
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.api.dependencies import get_identity_session
from app.db.base import Base
from app.security import auth_rate_limiter


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.api.dependencies import _get_source
    monkeypatch.setenv("MARKET_DATA_SOURCE", "mock")
    _get_source.cache_clear()
    try:
        yield TestClient(app)
    finally:
        _get_source.cache_clear()


@pytest.fixture
def identity_session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def identity_client(
    identity_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    from app.api.dependencies import _get_source

    def override_session() -> Generator[Session, None, None]:
        with identity_session_factory() as session:
            yield session

    monkeypatch.setenv("MARKET_DATA_SOURCE", "mock")
    _get_source.cache_clear()
    auth_rate_limiter.clear()
    app.dependency_overrides[get_identity_session] = override_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_identity_session, None)
        auth_rate_limiter.clear()
        _get_source.cache_clear()
