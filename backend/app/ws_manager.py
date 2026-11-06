from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.rooms: dict[int, set[WebSocket]] = {}
        self.user_rooms: dict[int, set[WebSocket]] = {}
        # 文档房间在线成员表：doc_id → { client_key: { name, offset } }
        self.rosters: dict[int, dict[str, dict]] = {}

    async def connect(self, doc_id: int, websocket: WebSocket) -> None:
        """把连接放进某篇文档的房间。"""
        await websocket.accept()
        self.rooms.setdefault(doc_id, set()).add(websocket)

    def disconnect(self, doc_id: int, websocket: WebSocket) -> None:
        """从文档房间移除连接。"""
        conns = self.rooms.get(doc_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self.rooms.pop(doc_id, None)

    async def broadcast(self, doc_id: int, event: str, data: Any) -> None:
        """向正在看这篇文档的连接推送事件。"""
        await self._send(self.rooms.get(doc_id, set()), event, data, self.disconnect, doc_id)

    async def connect_user(self, user_id: int, websocket: WebSocket) -> None:
        """把连接放进某个登录用户的房间，供首页收通知。"""
        await websocket.accept()
        self.user_rooms.setdefault(user_id, set()).add(websocket)

    def disconnect_user(self, user_id: int, websocket: WebSocket) -> None:
        """从用户房间移除连接。"""
        conns = self.user_rooms.get(user_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self.user_rooms.pop(user_id, None)

    async def broadcast_user(self, user_id: int, event: str, data: Any) -> None:
        """向该用户已打开的首页推送事件。"""
        await self._send(
            self.user_rooms.get(user_id, set()),
            event,
            data,
            self.disconnect_user,
            user_id,
        )

    async def _send(self, sockets, event: str, data: Any, drop, room_id: int) -> None:
        """把同一条消息发给一组连接，发失败的从房间清掉。"""
        payload = json.dumps({"event": event, "data": data}, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in list(sockets):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            drop(room_id, ws)

    async def relay(self, doc_id: int, exclude: WebSocket, event: str, data: Any) -> None:
        """把某条连接发来的消息转发给同房间的其他人，不回给发送者。"""
        conns = set(self.rooms.get(doc_id, set()))
        conns.discard(exclude)
        await self._send(conns, event, data, self.disconnect, doc_id)


manager = ConnectionManager()
