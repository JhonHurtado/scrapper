# tests/test_routes.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from backend.config import config
    from backend.database.db import close_db, init_db
    monkeypatch.setattr(config, "db_path", tmp_path / "test.db")
    close_db()
    init_db()
    from backend.main import app
    yield TestClient(app)
    close_db()


def test_scrape_status_idle(client):
    r = client.get("/api/scrape/status")
    assert r.status_code == 200
    data = r.json()
    assert data["running"] is False
    assert "placesCount" in data


def test_list_places_empty(client):
    r = client.get("/api/places")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_list_places_pagination(tmp_path, monkeypatch):
    from backend.config import config
    from backend.database.db import close_db, init_db
    from backend.database.models import Place, save_place
    monkeypatch.setattr(config, "db_path", tmp_path / "test.db")
    close_db()
    init_db()
    for i in range(5):
        save_place(Place(name=f"Lugar {i}", city="Bogotá",
                         department="Cundinamarca", category="nature"))
    from backend.main import app
    c = TestClient(app)
    r = c.get("/api/places?page=1&per_page=3")
    data = r.json()
    assert data["total"] == 5
    assert len(data["places"]) == 3


def test_websocket_connects(client):
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert "session_id" in msg
