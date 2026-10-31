import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import logging
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import (
    get_application_environment,
    get_cors_origins,
    get_websocket_connection_limit,
)
from app.services.live_state import live_state_store

router = APIRouter(tags=["websocket"])
logger = logging.getLogger(__name__)


def _normalized_origin(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _origin_is_allowed(websocket: WebSocket) -> bool:
    if get_application_environment() != "production":
        return True
    origin = _normalized_origin(websocket.headers.get("origin"))
    allowed = {_normalized_origin(value) for value in get_cors_origins()}
    return origin is not None and origin in allowed


class ConnectionManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> bool:
        if len(self.active) >= get_websocket_connection_limit():
            await websocket.close(code=1013, reason="Connection capacity reached")
            return False
        self.active.add(websocket)
        try:
            await websocket.accept()
        except Exception:
            self.active.discard(websocket)
            raise
        return True

    def disconnect(self, websocket: WebSocket) -> None:
        self.active.discard(websocket)

    async def broadcast(self, event: dict) -> None:
        dead = []
        for websocket in tuple(self.active):
            try:
                await websocket.send_json(event)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)


manager = ConnectionManager()


def _json(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if hasattr(value, "__dict__"):
        return _json(asdict(value))
    return value


@router.websocket("/ws/market")
async def market_socket(websocket: WebSocket) -> None:
    if not _origin_is_allowed(websocket):
        await websocket.close(code=1008, reason="Origin not allowed")
        return
    if not await manager.connect(websocket):
        return

    try:
        current = live_state_store.snapshot()
        await websocket.send_json({"type": "snapshot", "data": _json(current)})
        previous_quotes = {
            symbol: asdict(quote) for symbol, quote in current.quotes.items()
        }
        while True:
            await asyncio.sleep(1)
            current = live_state_store.snapshot()
            for symbol, quote in current.quotes.items():
                encoded = asdict(quote)
                if previous_quotes.get(symbol) != encoded:
                    await websocket.send_json(
                        {"type": "quote_update", "data": _json(encoded)}
                    )
            previous_quotes = {
                symbol: asdict(quote) for symbol, quote in current.quotes.items()
            }
            await websocket.send_json(
                {
                    "type": "heartbeat",
                    "server_timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.error("Unexpected market WebSocket failure")
    finally:
        manager.disconnect(websocket)
