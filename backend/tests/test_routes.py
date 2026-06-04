# backend/tests/test_routes.py
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture(autouse=True)
def reset_state():
    from backend.api import routes
    routes.state._running = False
    routes.state._paused = False
    yield
    routes.state._running = False
    routes.state._paused = False


@pytest.mark.asyncio
async def test_health_check():
    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "connections" in data


@pytest.mark.asyncio
async def test_scrape_status_not_running():
    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/scrape/status")
        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False


@pytest.mark.asyncio
async def test_start_scrape_already_running():
    from backend.main import app
    from backend.api import routes
    routes.state._running = True

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/scrape/start")
        assert response.status_code == 409

    routes.state._running = False


@pytest.mark.asyncio
async def test_pause_without_scrape_running():
    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/scrape/pause")
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_export_places():
    from backend.main import app
    from backend.database.models import Place, save_place

    place = Place(
        name="Test Place",
        city="Bogotá",
        department="Cundinamarca",
        category="monuments",
    )
    save_place(place)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/export/json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_list_places_pagination():
    from backend.main import app
    from backend.database.models import Place, save_place

    for i in range(60):
        place = Place(
            name=f"Place {i}",
            city="Bogotá" if i < 30 else "Medellín",
            department="Cundinamarca" if i < 30 else "Antioquia",
            category="monuments",
        )
        save_place(place)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/places?page=1&per_page=20")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 60
        assert data["page"] == 1
        assert data["perPage"] == 20
        assert len(data["places"]) == 20


@pytest.mark.asyncio
async def test_list_places_filter_by_city():
    from backend.main import app
    from backend.database.models import Place, save_place

    place1 = Place(name="Bogotá Place", city="Bogotá", department="Cundinamarca", category="monuments")
    place2 = Place(name="Medellín Place", city="Medellín", department="Antioquia", category="nature")
    save_place(place1)
    save_place(place2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/places?city=bogota")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["places"][0]["city"] == "Bogotá"


@pytest.mark.asyncio
async def test_invalid_page_parameter():
    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/places?page=0")
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_per_page_parameter():
    from backend.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/places?per_page=500")
        assert response.status_code == 422