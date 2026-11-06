from __future__ import annotations

import json

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import admin_auth, auth, comments, docs, folders, share
from app.routers.admin_auth import user_id_from_token
from app.settings import get_settings, load_settings
from app.ws_manager import manager

app = FastAPI(title="MD批注协作平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(docs.router)
app.include_router(share.router)
app.include_router(comments.router)
app.include_router(admin_auth.router)
app.include_router(auth.router)
app.include_router(folders.router)


@app.on_event("startup")
def on_startup():
    """启动时加载旁路配置并初始化数据库。"""
    load_settings()
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True, "service": "md-annotate"}


@app.get("/api/feature-flags")
def feature_flags():
    """公开的功能开关，前端据此决定是否启用光标 / 在线列表。"""
    s = get_settings()
    return {"oncursor": s.oncursor_enabled, "online": s.online_enabled}


@app.get("/api/entry")
def entry():
    """公开返回登录入口路径（config.ini 的 login_path）。

    登录已合并到该路径一页，未登录访客（含分享链接）据此跳转。
    """
    return {"login_path": get_settings().login_path}


@app.websocket("/ws/user")
async def ws_user(websocket: WebSocket, token: str | None = Query(default=None)):
    """作者首页订阅：批注变动时推送，用登录 token 认人。"""
    user_id = user_id_from_token(token)
    if user_id is None or not get_settings().oncursor_enabled:
        await websocket.accept()
        await websocket.close(code=1008)
        return
    await manager.connect_user(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_user(user_id, websocket)
    except Exception:
        manager.disconnect_user(user_id, websocket)


@app.websocket("/ws/doc/{doc_id}")
async def ws_doc(websocket: WebSocket, doc_id: int):
    """文档房间：转发光标与上线事件，并把在线名单推给晚进来的人。"""
    flags = get_settings()
    await manager.connect(doc_id, websocket)
    # 中文：新连接先拿到房间当前在线名单，不用等下一次心跳才发现人
    roster = manager.rosters.setdefault(doc_id, {})
    if roster:
        payload = {
            "event": "presence.list",
            "data": {"peers": [{"client_key": k, **v} for k, v in roster.items()]},
        }
        try:
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass
    client_key: str | None = None
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            event = msg.get("event")
            if event not in ("cursor", "join"):
                continue
            # 中文：开关把关——join 受 online 管，cursor 受 oncursor 管，关的直接丢弃
            if event == "join" and not flags.online_enabled:
                continue
            if event == "cursor" and not flags.oncursor_enabled:
                continue
            data = msg.get("data") or {}
            if not isinstance(data, dict):
                continue
            key = data.get("client_key")
            if not (isinstance(key, str) and key):
                continue
            client_key = key
            entry = roster.get(key) or {"name": "访客", "offset": None}
            if event == "join":
                entry["name"] = str(data.get("name") or "访客")
                await manager.relay(doc_id, websocket, "presence.join", data)
            else:
                entry["offset"] = data.get("offset")
                await manager.relay(doc_id, websocket, "cursor", data)
            roster[key] = entry
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        manager.disconnect(doc_id, websocket)
        if client_key:
            roster.pop(client_key, None)
            await manager.broadcast(
                doc_id, "peer.leave", {"client_key": client_key}
            )
