# backend/tests/test_websocket.py
import pytest
import asyncio
from backend.api.websocket import ConnectionManager


class MockWebSocket:
    def __init__(self):
        self.accepted = False
        self.sent_messages = []
        self.closed = False
        self.headers = {}
        self._id = id(self)

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        self.sent_messages.append(data)

    async def send_text(self, data):
        self.sent_messages.append(data)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_connection_manager_connect():
    manager = ConnectionManager()
    ws = MockWebSocket()
    session_id = await manager.connect(ws)
    assert ws.accepted is True
    assert session_id is not None
    assert manager.connection_count == 1


@pytest.mark.asyncio
async def test_connection_manager_disconnect():
    manager = ConnectionManager()
    ws = MockWebSocket()
    session_id = await manager.connect(ws)
    await manager.disconnect(ws)
    assert manager.connection_count == 0


@pytest.mark.asyncio
async def test_connection_manager_broadcast():
    manager = ConnectionManager()
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    await manager.connect(ws1)
    await manager.connect(ws2)

    await manager.broadcast({"type": "test", "message": "hello"})
    assert len(ws1.sent_messages) == 1
    assert len(ws2.sent_messages) == 1


@pytest.mark.asyncio
async def test_connection_manager_send_to():
    manager = ConnectionManager()
    ws = MockWebSocket()
    session_id = await manager.connect(ws)

    await manager.send_to(session_id, {"type": "direct", "message": "hello"})
    assert len(ws.sent_messages) == 1
    assert ws.sent_messages[0]["type"] == "direct"