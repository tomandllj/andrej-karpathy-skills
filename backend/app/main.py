from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import comments, docs, share
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


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"ok": True, "service": "md-annotate"}


@app.websocket("/ws/doc/{doc_id}")
async def ws_doc(websocket: WebSocket, doc_id: int):
    await manager.connect(doc_id, websocket)
    try:
        while True:
            # keep-alive / ignore client messages in phase 1
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(doc_id, websocket)
    except Exception:
        manager.disconnect(doc_id, websocket)
