"""Bounded deployment smoke tests for approved local or remote targets."""

import argparse
import json
from typing import Callable
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class SmokeTestError(RuntimeError):
    pass


def _is_local_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }


def _validate_target(url: str, allow_remote: bool) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise SmokeTestError("Target must be a valid HTTP(S) origin") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise SmokeTestError("Target must be an HTTP(S) origin without credentials")
    if not allow_remote and not _is_local_url(url):
        raise SmokeTestError("Remote targets require explicit --allow-remote approval")
    return url.rstrip("/")


def _fetch_json(
    url: str, timeout: float, opener: Callable
):
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with opener(request, timeout=timeout) as response:
            if response.status != 200:
                raise SmokeTestError(f"{url} returned HTTP {response.status}")
            return json.loads(response.read())
    except SmokeTestError:
        raise
    except Exception as exc:
        raise SmokeTestError(f"Request failed for {url}: {exc}") from exc


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeTestError(message)


def _check_websocket(api_base_url: str, origin: str, timeout: float) -> None:
    from websockets.sync.client import connect

    parsed = urlsplit(api_base_url)
    websocket_scheme = "wss" if parsed.scheme == "https" else "ws"
    websocket_url = f"{websocket_scheme}://{parsed.netloc}/api/v1/ws/market"
    try:
        with connect(
            websocket_url,
            origin=origin,
            open_timeout=timeout,
            close_timeout=timeout,
        ) as websocket:
            message = json.loads(websocket.recv(timeout=timeout))
    except Exception as exc:
        raise SmokeTestError("WebSocket handshake or snapshot failed") from exc
    _require(message.get("type") == "snapshot", "WebSocket did not send a snapshot")


def run_smoke_tests(
    *,
    api_base_url: str,
    frontend_url: str,
    timeout: float = 5,
    allow_remote: bool = False,
    websocket: bool = False,
    websocket_origin: str | None = None,
    opener: Callable = urlopen,
) -> list[str]:
    if not 1 <= timeout <= 30:
        raise SmokeTestError("timeout must be between 1 and 30 seconds")
    api = _validate_target(api_base_url, allow_remote)
    frontend = _validate_target(frontend_url, allow_remote)
    checks: list[str] = []

    live = _fetch_json(f"{api}/api/v1/health/live", timeout, opener)
    _require(live == {"status": "ok", "service": "marketmitra-api"}, "Liveness contract failed")
    checks.append("liveness")

    ready = _fetch_json(f"{api}/api/v1/health/ready", timeout, opener)
    _require(ready == {"status": "ready", "service": "marketmitra-api"}, "Readiness contract failed")
    checks.append("readiness")

    health = _fetch_json(f"{api}/api/v1/health", timeout, opener)
    overview = _fetch_json(f"{api}/api/v1/market/overview", timeout, opener)
    _require(isinstance(health, dict), "Health response structure failed")
    _require(isinstance(overview, dict), "Market overview must be an object")
    _require(health.get("enabled") is False, "Live polling must be disabled")
    _require(
        overview.get("data_freshness") in {"HISTORICAL", "DELAYED"},
        "Deployment data must be labeled historical or delayed",
    )
    checks.append("historical-demo-label")
    _require(
        {"nepse_index", "market_status", "last_updated"} <= overview.keys(),
        "Market overview structure failed",
    )
    checks.append("market-overview")

    stocks = _fetch_json(f"{api}/api/v1/stocks", timeout, opener)
    _require(
        isinstance(stocks, list) and stocks and isinstance(stocks[0], dict),
        "Stock listing is empty or invalid",
    )
    symbol = stocks[0].get("symbol")
    _require(isinstance(symbol, str) and symbol, "Stock symbol is missing")
    query = urlencode({"q": symbol})
    search = _fetch_json(f"{api}/api/v1/stocks?{query}", timeout, opener)
    _require(
        isinstance(search, list)
        and all(isinstance(item, dict) for item in search)
        and any(item.get("symbol") == symbol for item in search),
        "Stock search failed",
    )
    checks.append("stock-list-search")

    detail = _fetch_json(f"{api}/api/v1/stocks/{symbol}", timeout, opener)
    history = _fetch_json(f"{api}/api/v1/stocks/{symbol}/history", timeout, opener)
    _require(
        isinstance(detail, dict) and detail.get("symbol") == symbol,
        "Stock detail structure failed",
    )
    _require(
        isinstance(history, list) and history and isinstance(history[0], dict),
        "Stock history is empty or invalid",
    )
    _require({"date", "open", "high", "low", "close", "volume"} <= history[0].keys(), "Stock history structure failed")
    checks.append("stock-detail-history")

    sectors = _fetch_json(f"{api}/api/v1/market/sectors", timeout, opener)
    heatmap = _fetch_json(f"{api}/api/v1/market/heatmap", timeout, opener)
    _require(isinstance(sectors, list), "Sector response must be a list")
    _require(isinstance(heatmap, list), "Heatmap response must be a list")
    checks.append("sector-heatmap")

    request = Request(f"{frontend}/", headers={"Accept": "text/html"})
    try:
        with opener(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            content_type = response.headers.get("Content-Type", "")
    except Exception as exc:
        raise SmokeTestError(f"Frontend request failed: {exc}") from exc
    _require(response.status == 200 and "text/html" in content_type, "Frontend availability failed")
    _require('id="root"' in body, "Frontend root element is missing")
    checks.append("frontend")

    if websocket:
        if not websocket_origin:
            raise SmokeTestError("WebSocket checks require --websocket-origin")
        _check_websocket(api, websocket_origin, timeout)
        checks.append("websocket")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", required=True)
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--websocket", action="store_true")
    parser.add_argument("--websocket-origin")
    args = parser.parse_args()
    try:
        checks = run_smoke_tests(
            api_base_url=args.api_base_url,
            frontend_url=args.frontend_url,
            timeout=args.timeout,
            allow_remote=args.allow_remote,
            websocket=args.websocket,
            websocket_origin=args.websocket_origin,
        )
    except SmokeTestError as exc:
        print(f"SMOKE TEST FAILED: {exc}")
        return 2
    print(f"Smoke tests passed: {', '.join(checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
