"""Small, single-instance HTTP boundary controls."""

from collections import deque
import math
import time
from typing import Callable
from urllib.parse import urlsplit

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.config import (
    get_application_environment,
    get_http_rate_limit,
    get_trusted_hosts,
    hsts_enabled,
)

_HEALTH_PATHS = {"/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready"}
_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src 'self' data: https://fastapi.tiangolo.com"
)


class InMemoryRateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._requests: dict[str, deque[float]] = {}
        self._last_cleanup = 0.0

    def clear(self) -> None:
        self._requests.clear()
        self._last_cleanup = 0.0

    def check(self, client: str, limit: int, window: int, max_clients: int) -> int | None:
        now = self._clock()
        cutoff = now - window
        if now - self._last_cleanup >= window:
            stale_clients = [
                key
                for key, timestamps in self._requests.items()
                if not timestamps or timestamps[-1] <= cutoff
            ]
            for key in stale_clients:
                self._requests.pop(key, None)
            self._last_cleanup = now

        timestamps = self._requests.get(client)
        if timestamps is None:
            if len(self._requests) >= max_clients:
                oldest = min(self._requests, key=lambda key: self._requests[key][-1])
                self._requests.pop(oldest, None)
            timestamps = self._requests[client] = deque()
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()
        if len(timestamps) >= limit:
            return max(1, math.ceil(window - (now - timestamps[0])))
        timestamps.append(now)
        return None


http_rate_limiter = InMemoryRateLimiter()
# shortcut: per-process auth limits are single-instance only; use a shared store before scaling out.
auth_rate_limiter = InMemoryRateLimiter()


def _hostname(host_header: str) -> str | None:
    try:
        parsed = urlsplit(f"//{host_header}")
        parsed.port
    except ValueError:
        return None
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        return None
    return parsed.hostname.lower() if parsed.hostname else None


def _add_security_headers(response: Response) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = _CONTENT_SECURITY_POLICY
    if hsts_enabled():
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )


class RuntimeSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if get_application_environment() != "production":
            return await call_next(request)

        host = _hostname(request.headers.get("host", ""))
        if host not in get_trusted_hosts():
            response: Response = JSONResponse(
                {"detail": "Invalid host header"}, status_code=400
            )
            _add_security_headers(response)
            return response

        if request.url.path not in _HEALTH_PATHS:
            limit, window, max_clients = get_http_rate_limit()
            client = request.client.host if request.client else "unknown"
            retry_after = http_rate_limiter.check(client, limit, window, max_clients)
            if retry_after is not None:
                response = JSONResponse(
                    {"detail": "Too many requests"},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
                _add_security_headers(response)
                return response

        response = await call_next(request)
        _add_security_headers(response)
        return response
