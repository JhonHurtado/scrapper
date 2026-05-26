# backend/api/routes.py
import asyncio
import logging
from dataclasses import dataclass, field

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse

from ..database.models import get_all_places, count_places
from ..exporters.json_exporter import export_json
from .websocket import manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@dataclass
class ScrapeState:
    running: bool = False
    paused: bool = False
    current_city: str = ""
    cities_done: int = 0
    cities_total: int = 0
    errors: int = 0


state = ScrapeState()


@router.post("/scrape/start")
async def start_scrape(background_tasks: BackgroundTasks):
    if state.running:
        return {"status": "already_running"}
    state.running = True
    state.paused = False
    background_tasks.add_task(_run_scrape)
    return {"status": "started"}


async def _run_scrape():
    from ..scraper.playwright_scraper import scrape_all
    try:
        await scrape_all(manager, state)
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        await manager.broadcast({"type": "error", "message": str(e)})
    finally:
        state.running = False
        state.paused = False


@router.post("/scrape/pause")
async def pause_scrape():
    """Pausa al terminar la ciudad actual (no interrumpe mid-scraping)."""
    state.paused = True
    return {"status": "pausing"}


@router.post("/scrape/resume")
async def resume_scrape():
    state.paused = False
    return {"status": "resumed"}


@router.post("/scrape/stop")
async def stop_scrape():
    state.running = False
    state.paused = False
    return {"status": "stopped"}


@router.get("/scrape/status")
async def scrape_status():
    return {
        "running": state.running,
        "paused": state.paused,
        "current_city": state.current_city,
        "cities_done": state.cities_done,
        "cities_total": state.cities_total,
        "places": count_places(),
        "errors": state.errors,
    }


@router.get("/export/json")
async def export_places():
    path = export_json()
    return FileResponse(
        path=str(path),
        filename="places.json",
        media_type="application/json",
    )


@router.get("/places")
async def list_places(page: int = 1, per_page: int = 50):
    all_places = get_all_places()
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "total": len(all_places),
        "page": page,
        "per_page": per_page,
        "places": [p.to_dict() for p in all_places[start:end]],
    }
