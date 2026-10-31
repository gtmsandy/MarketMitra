"""Production HTTP security boundary contracts."""

from fastapi.testclient import TestClient

from app.main import app


def _production_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("TRUSTED_HOSTS", "api.example.com,health.example.com")
    return TestClient(app)


def test_production_accepts_configured_host_and_adds_security_headers(monkeypatch) -> None:
    client = _production_client(monkeypatch)

    response = client.get("/api/v1/health/live", headers={"host": "api.example.com"})

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "strict-transport-security" not in response.headers


def test_production_rejects_untrusted_host(monkeypatch) -> None:
    client = _production_client(monkeypatch)

    response = client.get("/api/v1/health/live", headers={"host": "evil.example"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid host header"}


def test_production_rejects_malformed_host_even_when_hostname_matches(monkeypatch) -> None:
    client = _production_client(monkeypatch)

    response = client.get(
        "/api/v1/health/live", headers={"host": "api.example.com/not-a-host"}
    )

    assert response.status_code == 400


def test_configured_health_check_host_is_accepted(monkeypatch) -> None:
    client = _production_client(monkeypatch)

    response = client.get(
        "/api/v1/health/live", headers={"host": "health.example.com"}
    )

    assert response.status_code == 200


def test_production_readiness_contract_remains_compatible(monkeypatch) -> None:
    from app.api.routes.health import get_readiness_checker

    client = _production_client(monkeypatch)
    app.dependency_overrides[get_readiness_checker] = lambda: lambda: None
    try:
        response = client.get(
            "/api/v1/health/ready", headers={"host": "health.example.com"}
        )
    finally:
        app.dependency_overrides.pop(get_readiness_checker, None)

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "marketmitra-api"}


def test_development_preserves_localhost_and_has_no_rate_limit(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("HTTP_RATE_LIMIT_REQUESTS", "1")
    client = TestClient(app)

    first = client.get("/api/v1/health/live", headers={"host": "localhost"})
    second = client.get("/api/v1/health/live", headers={"host": "localhost"})

    assert first.status_code == 200
    assert second.status_code == 200


def test_hsts_requires_explicit_https_deployment(monkeypatch) -> None:
    client = _production_client(monkeypatch)
    monkeypatch.setenv("HTTPS_DEPLOYMENT", "true")
    monkeypatch.setenv("HSTS_ENABLED", "true")

    response = client.get("/api/v1/health/live", headers={"host": "api.example.com"})

    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )


def test_production_rate_limit_recovers_and_exempts_health(monkeypatch) -> None:
    from app.security import http_rate_limiter

    client = _production_client(monkeypatch)
    monkeypatch.setenv("HTTP_RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("HTTP_RATE_LIMIT_WINDOW_SECONDS", "10")
    now = [100.0]
    monkeypatch.setattr(http_rate_limiter, "_clock", lambda: now[0])
    http_rate_limiter.clear()

    first = client.get(
        "/api/v1/market/summary", headers={"host": "api.example.com"}
    )
    assert first.status_code != 429
    limited = client.get(
        "/api/v1/market/summary", headers={"host": "api.example.com"}
    )
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "10"
    assert "testclient" not in limited.text

    health = client.get(
        "/api/v1/health/live", headers={"host": "api.example.com"}
    )
    assert health.status_code == 200
    now[0] = 111.0
    recovered = client.get(
        "/api/v1/market/summary", headers={"host": "api.example.com"}
    )
    assert recovered.status_code != 429
    http_rate_limiter.clear()


def test_rate_limit_ignores_spoofed_forwarded_address(monkeypatch) -> None:
    from app.security import http_rate_limiter

    client = _production_client(monkeypatch)
    monkeypatch.setenv("HTTP_RATE_LIMIT_REQUESTS", "1")
    http_rate_limiter.clear()

    first = client.get(
        "/api/v1/market/summary",
        headers={"host": "api.example.com", "x-forwarded-for": "198.51.100.1"},
    )
    second = client.get(
        "/api/v1/market/summary",
        headers={"host": "api.example.com", "x-forwarded-for": "203.0.113.2"},
    )

    assert first.status_code != 429
    assert second.status_code == 429
    http_rate_limiter.clear()


def test_rate_limiter_bounds_client_records(monkeypatch) -> None:
    from app.security import InMemoryRateLimiter

    now = [100.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])

    assert limiter.check("client-a", 1, 60, 2) is None
    now[0] += 1
    assert limiter.check("client-b", 1, 60, 2) is None
    now[0] += 1
    assert limiter.check("client-c", 1, 60, 2) is None

    assert len(limiter._requests) == 2
