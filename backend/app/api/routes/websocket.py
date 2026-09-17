import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.live_state import live_state_store

router = APIRouter(tags=["websocket"])

class ConnectionManager:
    def __init__(self): self.active: set[WebSocket] = set()
    async def connect(self, ws): await ws.accept(); self.active.add(ws)
    def disconnect(self, ws): self.active.discard(ws)
    async def broadcast(self, event):
        dead=[]
        for ws in tuple(self.active):
            try: await ws.send_json(event)
            except Exception: dead.append(ws)
        for ws in dead: self.disconnect(ws)

manager = ConnectionManager()

def _json(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, dict): return {k: _json(v) for k,v in value.items()}
    if hasattr(value, "__dict__"): return _json(asdict(value))
    return value

@router.websocket("/ws/market")
async def market_socket(ws: WebSocket):
    await manager.connect(ws)
    try:
        current = live_state_store.snapshot()
        await ws.send_json({"type":"snapshot", "data": _json(current)})
        previous_quotes = {k: asdict(v) for k, v in current.quotes.items()}
        while True:
            await asyncio.sleep(1)
            current = live_state_store.snapshot()
            for symbol, quote in current.quotes.items():
                encoded = asdict(quote)
                if previous_quotes.get(symbol) != encoded:
                    await ws.send_json({"type":"quote_update", "data": _json(encoded)})
            previous_quotes = {k: asdict(v) for k, v in current.quotes.items()}
            await ws.send_json({"type":"heartbeat", "server_timestamp": datetime.now(timezone.utc).isoformat()})
    except (WebSocketDisconnect, Exception):
        manager.disconnect(ws)
