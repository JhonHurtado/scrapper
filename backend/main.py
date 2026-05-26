# backend/main.py
import uuid
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .database.db import init_db
from .api.routes import router
from .api.websocket import manager

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Colombia Tourist Scraper", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def startup():
    init_db()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    session_id = str(uuid.uuid4())
    await manager.broadcast({"type": "connected", "session_id": session_id})
    try:
        while True:
            await websocket.receive_text()  # mantener conexión viva (ping)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
