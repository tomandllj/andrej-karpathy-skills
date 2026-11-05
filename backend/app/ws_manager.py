from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[int, set[WebSocket]] = {}

    async def connect(self, doc_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.rooms.setdefault(doc_id, set()).add(websocket)

    def disconnect(self, doc_id: int, websocket: WebSocket) -> None:
        conns = self.rooms.get(doc_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self.rooms.pop(doc_id, None)

    async def broadcast(self, doc_id: int, event: str, data: Any) -> None:
        payload = json.dumps({"event": event, "data": data}, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in list(self.rooms.get(doc_id, set())):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(doc_id, ws)


manager = ConnectionManager()
