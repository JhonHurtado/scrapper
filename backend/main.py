# backend/main.py
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .database.db import init_db
from .api.routes import router
from .api.websocket import manager

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Colombia Tourist Scraper", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    session_id = str(uuid.uuid4())
    # Send only to the connecting client, not all connected clients
    await websocket.send_json({"type": "connected", "session_id": session_id})
    try:
        while True:
            await websocket.receive_text()  # mantener conexión viva (ping)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
