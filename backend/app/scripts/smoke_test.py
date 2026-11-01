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


def _numeric_values(rows, field: str) -> list[float] | None:
    if not isinstance(rows, list) or not all(
        isinstance(item, dict) and isinstance(item.get(field), (int, float))
        for item in rows
    ):
        return None
    return [float(item[field]) for item in rows]


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
        isinstance(stocks, list) and stocks and all(isinstance(item, dict) for item in stocks),
        "Stock listing is empty or invalid",
    )
    symbol = stocks[0].get("symbol")
    _require(isinstance(symbol, str) and symbol, "Stock symbol is missing")
    _require(
        all(isinstance(item.get("symbol"), str) and item["symbol"].startswith("SYN") for item in stocks),
        "Stock listing contains a non-synthetic staging symbol",
    )
    _require(
        all(
            isinstance(item.get("company_name"), str)
            and item["company_name"].startswith("Synthetic ")
            for item in stocks
        ),
        "Stock listing is missing explicit synthetic-data labels",
    )
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
        isinstance(history, list) and len(history) >= 2 and isinstance(history[0], dict),
        "Stock history is empty or invalid",
    )
    _require({"date", "open", "high", "low", "close", "volume"} <= history[0].keys(), "Stock history structure failed")
    checks.append("stock-detail-history")

    gainers = _fetch_json(f"{api}/api/v1/market/gainers", timeout, opener)
    losers = _fetch_json(f"{api}/api/v1/market/losers", timeout, opener)
    active = _fetch_json(f"{api}/api/v1/market/most-active", timeout, opener)
    gainer_changes = _numeric_values(gainers, "change_percent")
    loser_changes = _numeric_values(losers, "change_percent")
    active_turnovers = _numeric_values(active, "turnover")
    _require(
        bool(gainer_changes)
        and all(value > 0 for value in gainer_changes)
        and gainer_changes == sorted(gainer_changes, reverse=True),
        "Gainers are empty, invalid, or incorrectly ranked",
    )
    _require(
        bool(loser_changes)
        and all(value < 0 for value in loser_changes)
        and loser_changes == sorted(loser_changes),
        "Losers are empty, invalid, or incorrectly ranked",
    )
    _require(
        bool(active_turnovers)
        and active_turnovers == sorted(active_turnovers, reverse=True),
        "Most-active stocks are empty, invalid, or incorrectly ranked",
    )
    _require(gainers[0].get("symbol") == "SYNBANKA", "Unexpected leading synthetic gainer")
    _require(losers[0].get("symbol") == "SYNBANKB", "Unexpected leading synthetic loser")
    _require(active[0].get("symbol") == "SYNBANKB", "Unexpected leading most-active stock")
    checks.append("market-movers")

    sectors = _fetch_json(f"{api}/api/v1/market/sectors", timeout, opener)
    _require(
        isinstance(sectors, list) and len(sectors) == 3
        and all(isinstance(item, dict) for item in sectors)
        and all(item.get("sector", "").startswith("Synthetic ") for item in sectors)
        and all(item.get("stock_count") == 2 for item in sectors),
        "Sector analytics do not match the approved synthetic fixture",
    )
    checks.append("sector-analytics")

    heatmap = _fetch_json(f"{api}/api/v1/market/heatmap", timeout, opener)
    heatmap_turnovers = _numeric_values(heatmap, "turnover")
    _require(
        isinstance(heatmap, list) and len(heatmap) == 6
        and all(isinstance(item, dict) for item in heatmap)
        and all(item.get("symbol", "").startswith("SYN") for item in heatmap)
        and bool(heatmap_turnovers)
        and heatmap_turnovers == sorted(heatmap_turnovers, reverse=True),
        "Heatmap does not match the approved synthetic fixture",
    )
    checks.append("heatmap")

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
