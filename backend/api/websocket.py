# backend/api/websocket.py
import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

from ..config import config

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        session_id = websocket.headers.get("sec-websocket-key", "")[:16] or str(id(websocket))
        async with self._lock:
            self._connections[session_id] = websocket

        self._heartbeat_tasks[session_id] = asyncio.create_task(
            self._heartbeat(session_id)
        )
        logger.info(f"WS connected. Total: {len(self._connections)}")
        return session_id

    async def disconnect(self, websocket: WebSocket):
        session_id = await self._find_session_id(websocket)
        if session_id:
            async with self._lock:
                self._connections.pop(session_id, None)
            task = self._heartbeat_tasks.pop(session_id, None)
            if task:
                task.cancel()
            logger.info(f"WS disconnected. Total: {len(self._connections)}")

    async def _find_session_id(self, websocket: WebSocket) -> str:
        async with self._lock:
            for sid, conn in self._connections.items():
                if conn == websocket:
                    return sid
        return ""

    async def _heartbeat(self, session_id: str):
        try:
            while True:
                await asyncio.sleep(config.ws_heartbeat)
                async with self._lock:
                    conn = self._connections.get(session_id)
                if conn:
                    try:
                        await conn.send_json({"type": "heartbeat"})
                    except Exception:
                        break
        except asyncio.CancelledError:
            pass

    async def send_to(self, session_id: str, message: dict):
        async with self._lock:
            conn = self._connections.get(session_id)
        if conn:
            await conn.send_json(message)

    async def broadcast(self, message: dict):
        if not self._connections:
            return
        data = json.dumps(message, ensure_ascii=False, default=str)
        dead = []
        async with self._lock:
            connections = list(self._connections.items())

        for session_id, conn in connections:
            try:
                await conn.send_text(data)
            except Exception:
                dead.append(session_id)

        for session_id in dead:
            await self.disconnect_by_id(session_id)

    async def disconnect_by_id(self, session_id: str):
        async with self._lock:
            conn = self._connections.pop(session_id, None)
        task = self._heartbeat_tasks.pop(session_id, None)
        if task:
            task.cancel()
        if conn:
            try:
                await conn.close()
            except Exception:
                pass

    @property
    def connection_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()